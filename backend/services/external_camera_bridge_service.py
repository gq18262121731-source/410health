from __future__ import annotations

import json
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import requests

from backend.services.posture_event_service import PostureEventService
from backend.services.posture_knowledge_service import PostureKnowledgeService
from backend.services.target_pose_service import TargetPoseService
from backend.services.target_user_fall_service import TargetUserFallService


@dataclass(slots=True)
class ExternalCameraEndpoints:
    viewer_url: str = "http://127.0.0.1:8090/viewer"
    health_url: str = "http://127.0.0.1:8090/api/v1/camera/health"
    snapshot_url: str = "http://127.0.0.1:8090/api/v1/camera/snapshot"
    mjpeg_url: str = "http://127.0.0.1:8090/api/v1/camera/stream.mjpg"


class ExternalCameraBridgeService:
    """Bridge the local camera runtime into the target-only fall detection pipeline."""

    def __init__(
        self,
        *,
        data_root: Path,
        target_user_fall_service: TargetUserFallService,
        target_pose_service: TargetPoseService,
        posture_event_service: PostureEventService,
        posture_knowledge_service: PostureKnowledgeService,
    ) -> None:
        self._data_root = data_root
        self._target_user_fall_service = target_user_fall_service
        self._target_pose_service = target_pose_service
        self._posture_event_service = posture_event_service
        self._posture_knowledge_service = posture_knowledge_service
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
        image_bytes = self._fetch_latest_image_bytes()
        return self.detect_image_bytes(
            image_bytes,
            session_id=session_id,
            target_only=target_only,
            include_annotated_image=include_annotated_image,
            camera_source={
                "viewer_url": self._endpoints.viewer_url,
                "snapshot_url": self._endpoints.snapshot_url,
                "mjpeg_url": self._endpoints.mjpeg_url,
                "source_kind": "external_camera",
            },
        )

    def detect_image_bytes(
        self,
        image_bytes: bytes,
        *,
        session_id: str,
        target_only: bool = True,
        include_annotated_image: bool = False,
        camera_source: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = self._target_user_fall_service.detect(
            image_bytes,
            include_annotated_image=include_annotated_image,
            target_only=target_only,
            session_id=session_id,
        )
        target_pose = self._estimate_target_pose(image_bytes=image_bytes, result=result, session_id=session_id)
        posture_event = self._posture_event_service.analyze(
            session_id=session_id,
            pose_result=target_pose,
            target_matched=bool((result.get("target_match") or {}).get("matched")),
        )
        posture_guidance = None
        if posture_event is not None:
            posture_guidance = self._posture_knowledge_service.get(str(posture_event.get("type") or "normal"))
        diagnostics = self._build_diagnostics(result)
        result["diagnostics"] = diagnostics
        result["target_pose"] = target_pose
        result["posture_event"] = posture_event
        result["posture_guidance"] = posture_guidance
        result["camera_source"] = camera_source or {}
        result["bridge_latency_ms"] = int((time.perf_counter() - started) * 1000)
        result["snapshot_bytes"] = len(image_bytes)
        if diagnostics["is_failure"]:
            self._store_failure_frame(image_bytes=image_bytes, session_id=session_id, diagnostics=diagnostics)
        return result

    def _fetch_latest_image_bytes(self) -> bytes:
        errors: list[str] = []

        for attempt in range(2):
            try:
                response = self._session.get(self._endpoints.snapshot_url, timeout=10)
                response.raise_for_status()
                content = response.content
                if content.startswith(b"\xff\xd8") and len(content) > 1000:
                    return content
                errors.append(f"snapshot_invalid_jpeg_attempt_{attempt + 1}")
            except requests.RequestException as exc:
                errors.append(f"snapshot_attempt_{attempt + 1}:{exc.__class__.__name__}:{exc}")
                time.sleep(0.35)

        try:
            return self._fetch_frame_from_mjpeg()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"mjpeg_fallback:{exc.__class__.__name__}:{exc}")

        raise requests.HTTPError(" ; ".join(errors) or "EXTERNAL_CAMERA_FETCH_FAILED")

    def _fetch_frame_from_mjpeg(self) -> bytes:
        response = self._session.get(self._endpoints.mjpeg_url, timeout=15, stream=True)
        response.raise_for_status()

        buffer = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                buffer.extend(chunk)
                start = buffer.find(b"\xff\xd8")
                end = buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                if start >= 0 and end >= 0:
                    frame = bytes(buffer[start:end + 2])
                    if frame.startswith(b"\xff\xd8") and len(frame) > 1000:
                        return frame
                    break
                if len(buffer) > 2_000_000:
                    buffer = buffer[-256_000:]
        finally:
            response.close()

        raise RuntimeError("MJPEG_FRAME_NOT_FOUND")

    def _estimate_target_pose(self, *, image_bytes: bytes, result: dict[str, Any], session_id: str) -> dict[str, Any] | None:
        np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        tracking = result.get("tracking") or {}
        roi = tracking.get("roi") if isinstance(tracking.get("roi"), dict) else {}
        bbox = roi.get("bbox") if isinstance(roi, dict) else None
        track_id = tracking.get("track_id")
        try:
            return self._target_pose_service.estimate_pose(
                frame,
                bbox=bbox,
                session_id=session_id,
                track_id=track_id,
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"{exc.__class__.__name__}: {exc}",
                "pose": {"points": [], "connections": [], "posture": {"label": "unknown", "severity": "normal", "confidence": 0.0}},
            }

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
