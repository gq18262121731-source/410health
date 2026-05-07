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

    def health(self) -> dict[str, Any]:
        started = time.perf_counter()
        response = self._session.get(self._endpoints.health_url, timeout=10)
        response.raise_for_status()
        payload = response.json()
        payload["bridge_latency_ms"] = int((time.perf_counter() - started) * 1000)
        payload["viewer_url"] = self._endpoints.viewer_url
        payload["snapshot_url"] = self._endpoints.snapshot_url
        payload["mjpeg_url"] = self._endpoints.mjpeg_url
        return payload

    def detect_latest(
        self,
        *,
        session_id: str,
        target_only: bool = True,
        include_annotated_image: bool = False,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        response = self._session.get(self._endpoints.snapshot_url, timeout=10)
        response.raise_for_status()
        image_bytes = response.content
        result = self._target_user_fall_service.detect(
            image_bytes,
            include_annotated_image=include_annotated_image,
            target_only=target_only,
            session_id=session_id,
        )
        diagnostics = self._build_diagnostics(result)
        result["diagnostics"] = diagnostics
        result["camera_source"] = {
            "viewer_url": self._endpoints.viewer_url,
            "snapshot_url": self._endpoints.snapshot_url,
            "mjpeg_url": self._endpoints.mjpeg_url,
        }
        result["bridge_latency_ms"] = int((time.perf_counter() - started) * 1000)
        result["snapshot_bytes"] = len(image_bytes)
        if diagnostics["is_failure"]:
            self._store_failure_frame(image_bytes=image_bytes, session_id=session_id, diagnostics=diagnostics)
        return result

    def _build_diagnostics(self, result: dict[str, Any]) -> dict[str, Any]:
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
