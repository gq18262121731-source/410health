from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import requests

from backend.services.target_user_fall_service import TargetUserFallService


@dataclass(slots=True)
class ExternalCameraEndpoints:
    viewer_url: str = "http://127.0.0.1:8090/viewer"
    health_url: str = "http://127.0.0.1:8090/api/v1/camera/health"
    snapshot_url: str = "http://127.0.0.1:8090/api/v1/camera/snapshot"
    mjpeg_url: str = "http://127.0.0.1:8090/api/v1/camera/stream.mjpg"
    switch_url: str = "http://127.0.0.1:8090/api/v1/camera/stream/switch"


class ExternalCameraBridgeService:
    """Bridge the local camera runtime into the target-only fall detection pipeline."""

    def __init__(self, *, data_root: Path, target_user_fall_service: TargetUserFallService) -> None:
        self._data_root = data_root
        self._target_user_fall_service = target_user_fall_service
        self._endpoints = ExternalCameraEndpoints()
        self._session = requests.Session()
        self._session.headers.update({"Cache-Control": "no-store"})
        self._debug_root = self._data_root / "external_camera_debug"
        self._debug_root.mkdir(parents=True, exist_ok=True)
        self._max_debug_frames = 20
        self._max_snapshot_age_seconds = 3.0

    def health(self) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            response = self._session.get(self._endpoints.health_url, timeout=3)
            response.raise_for_status()
            payload = response.json()
            payload["bridge_status"] = "ok"
        except (requests.RequestException, ValueError) as exc:
            payload = {
                "running": False,
                "has_frame": False,
                "fresh_frame": False,
                "stale_frame": True,
                "frame_age_seconds": None,
                "last_error": str(exc),
                "bridge_status": "camera_unavailable",
            }
        payload["bridge_latency_ms"] = int((time.perf_counter() - started) * 1000)
        payload.update(self._camera_source())
        return payload

    def detect_latest(
        self,
        *,
        session_id: str,
        target_only: bool = True,
        include_annotated_image: bool = False,
        speed_mode: str = "balanced",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        camera_health = self.health()
        if camera_health.get("bridge_status") == "camera_unavailable" or not camera_health.get("has_frame"):
            return self._camera_failure_response(
                status="camera_unavailable",
                reason="CAMERA_UNAVAILABLE",
                message="External camera runtime is not reachable or has no frame yet.",
                started=started,
                camera_health=camera_health,
                session_id=session_id,
            )

        health_age = camera_health.get("frame_age_seconds")
        if isinstance(health_age, (int, float)) and health_age > self._max_snapshot_age_seconds:
            return self._camera_failure_response(
                status="camera_frame_stale",
                reason="CAMERA_FRAME_STALE",
                message=f"External camera frame is stale ({health_age:.1f}s old).",
                started=started,
                camera_health=camera_health,
                session_id=session_id,
            )

        try:
            response = self._session.get(self._endpoints.snapshot_url, timeout=5)
            response.raise_for_status()
        except requests.RequestException as exc:
            return self._camera_failure_response(
                status="camera_snapshot_failed",
                reason="CAMERA_SNAPSHOT_FAILED",
                message=str(exc),
                started=started,
                camera_health=camera_health,
                session_id=session_id,
            )

        snapshot_meta = self._snapshot_meta_from_headers(response.headers)
        if snapshot_meta.get("stale"):
            return self._camera_failure_response(
                status="camera_frame_stale",
                reason="CAMERA_FRAME_STALE",
                message="External camera snapshot header reports a stale frame.",
                started=started,
                camera_health=camera_health,
                snapshot_meta=snapshot_meta,
                session_id=session_id,
            )

        image_bytes = response.content
        result = self._target_user_fall_service.detect(
            image_bytes,
            include_annotated_image=include_annotated_image,
            target_only=target_only,
            session_id=session_id,
            speed_mode=speed_mode,
        )
        diagnostics = self._build_diagnostics(result, camera_health=camera_health, snapshot_meta=snapshot_meta)
        result["diagnostics"] = diagnostics
        result["camera_source"] = self._camera_source()
        result["camera_health"] = camera_health
        result["camera_frame"] = {**snapshot_meta, "snapshot_bytes": len(image_bytes)}
        result["bridge_latency_ms"] = int((time.perf_counter() - started) * 1000)
        result["snapshot_bytes"] = len(image_bytes)
        if diagnostics["is_failure"]:
            self._store_failure_frame(image_bytes=image_bytes, session_id=session_id, diagnostics=diagnostics)
        return result

    def refresh_stream(self, *, prefer_stream: str | None = None) -> dict[str, Any]:
        """Ask the camera runtime to reopen/switch the RTSP stream without reloading the web page."""
        started = time.perf_counter()
        before = self.health()
        current = str(before.get("current_stream") or before.get("stream") or "av0_0")
        if prefer_stream in {"av0_0", "av0_1"}:
            next_stream = prefer_stream
        else:
            next_stream = "av0_1" if current == "av0_0" else "av0_0"

        try:
            response = self._session.post(
                self._endpoints.switch_url,
                params={"stream": next_stream},
                timeout=6,
            )
            response.raise_for_status()
            switch_payload = response.json()
            switch_ok = True
            error = None
        except (requests.RequestException, ValueError) as exc:
            switch_payload = {}
            switch_ok = False
            error = str(exc)

        after = self._wait_for_fresh_camera_frame(timeout_seconds=6.0)
        return {
            "ok": switch_ok,
            "requested_stream": next_stream,
            "before": before,
            "after": after,
            "switch": switch_payload,
            "error": error,
            "bridge_latency_ms": int((time.perf_counter() - started) * 1000),
            **self._camera_source(),
        }

    def _wait_for_fresh_camera_frame(self, *, timeout_seconds: float) -> dict[str, Any]:
        deadline = time.perf_counter() + timeout_seconds
        last_health = self.health()
        while time.perf_counter() < deadline:
            age = last_health.get("frame_age_seconds")
            if (
                last_health.get("has_frame")
                and isinstance(age, (int, float))
                and age <= self._max_snapshot_age_seconds
                and not last_health.get("stale_frame")
            ):
                return last_health
            time.sleep(0.5)
            last_health = self.health()
        return last_health

    def _camera_source(self) -> dict[str, str]:
        return {
            "viewer_url": self._endpoints.viewer_url,
            "snapshot_url": self._endpoints.snapshot_url,
            "mjpeg_url": self._endpoints.mjpeg_url,
        }

    def _snapshot_meta_from_headers(self, headers: requests.structures.CaseInsensitiveDict[str]) -> dict[str, Any]:
        age_ms = self._parse_int(headers.get("X-Camera-Frame-Age-Ms"))
        frame_count = self._parse_int(headers.get("X-Camera-Frame-Count"))
        stale_header = str(headers.get("X-Camera-Frame-Stale") or "0").strip().lower()
        age_seconds = None if age_ms is None else age_ms / 1000.0
        return {
            "frame_age_ms": age_ms,
            "frame_age_seconds": age_seconds,
            "frame_count": frame_count,
            "stale": stale_header in {"1", "true", "yes"} or (
                age_seconds is not None and age_seconds > self._max_snapshot_age_seconds
            ),
        }

    def _parse_int(self, value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    def _camera_failure_response(
        self,
        *,
        status: str,
        reason: str,
        message: str,
        started: float,
        camera_health: dict[str, Any],
        session_id: str,
        snapshot_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        diagnostics = {
            "is_failure": True,
            "reasons": [reason],
            "warnings": [message],
            "candidate_count": 0,
            "track_id": None,
            "used_track": False,
            "used_roi": False,
            "match_decision": "camera_unavailable",
            "face_score": 0.0,
            "body_score": 0.0,
            "fused_score": 0.0,
            "fall_status": None,
            "camera_health": camera_health,
            "camera_frame": snapshot_meta or {},
        }
        return {
            "ok": False,
            "status": status,
            "error": message,
            "target_match": None,
            "fall_result": None,
            "pose_result": None,
            "posture_event": None,
            "posture_guidance": None,
            "warnings": [message],
            "tracking": {
                "session_id": session_id,
                "track_id": None,
                "used_track": False,
                "candidate_count": 0,
                "roi": {"used_roi": False},
            },
            "diagnostics": diagnostics,
            "camera_source": self._camera_source(),
            "camera_health": camera_health,
            "camera_frame": snapshot_meta or {},
            "bridge_latency_ms": int((time.perf_counter() - started) * 1000),
            "snapshot_bytes": 0,
        }

    def _build_diagnostics(
        self,
        result: dict[str, Any],
        *,
        camera_health: dict[str, Any] | None = None,
        snapshot_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        warnings = [str(item) for item in (result.get("warnings") or [])]
        tracking = result.get("tracking") or {}
        target_match = result.get("target_match") or {}
        fall_result = result.get("fall_result") or {}
        reasons: list[str] = []
        if "FACE_NOT_FOUND" in warnings:
            reasons.append("FACE_NOT_FOUND")
        if "BODY_NOT_FOUND" in warnings:
            reasons.append("BODY_NOT_FOUND")
        if not tracking.get("used_track"):
            reasons.append("NO_TRACK_CANDIDATE")
        if target_match.get("decision") in {"unknown", "non_target"}:
            reasons.append("LOW_MATCH_CONFIDENCE")
        if not reasons and result.get("status") == "filtered_non_target":
            reasons.append("FILTERED_NON_TARGET")
        return {
            "is_failure": result.get("status") == "filtered_non_target" or bool(warnings),
            "reasons": reasons,
            "warnings": warnings,
            "candidate_count": int(tracking.get("candidate_count") or 0),
            "track_id": tracking.get("track_id"),
            "used_track": bool(tracking.get("used_track")),
            "used_roi": bool((tracking.get("roi") or {}).get("used_roi")),
            "match_decision": target_match.get("decision", "unknown"),
            "face_score": float(target_match.get("face_score") or 0.0),
            "body_score": float(target_match.get("body_score") or 0.0),
            "fused_score": float(target_match.get("fused_score") or 0.0),
            "fall_status": fall_result.get("status"),
            "camera_health": camera_health or {},
            "camera_frame": snapshot_meta or {},
        }

    def _store_failure_frame(self, *, image_bytes: bytes, session_id: str, diagnostics: dict[str, Any]) -> None:
        session_dir = self._debug_root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time() * 1000)
        image_path = session_dir / f"{stamp}.jpg"
        meta_path = session_dir / f"{stamp}.json"
        image_path.write_bytes(image_bytes)
        meta_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

        images = sorted(session_dir.glob("*.jpg"))
        metas = sorted(session_dir.glob("*.json"))
        while len(images) > self._max_debug_frames:
            oldest = images.pop(0)
            oldest.unlink(missing_ok=True)
        while len(metas) > self._max_debug_frames:
            oldest = metas.pop(0)
            oldest.unlink(missing_ok=True)
