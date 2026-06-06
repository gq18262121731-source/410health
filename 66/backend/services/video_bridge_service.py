from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from backend.config import get_settings
from backend.models.video_bridge_model import (
    VideoAnalysisIngestResponse,
    VideoAnalysisPushRequest,
    VideoBridgeStatusResponse,
)
from backend.services.video_adapter import ADAPTER_VERSION, VideoAnalysisAdapter


class VideoBridgeService:
    """In-memory bridge for standalone video analysis service telemetry."""

    def __init__(self, adapter: VideoAnalysisAdapter | None = None) -> None:
        self._adapter = adapter or VideoAnalysisAdapter()
        self._records: dict[tuple[str, str], object] = {}
        self._updated_at = datetime.now(timezone.utc)
        self._settings = get_settings()
        self._session = requests.Session()
        self._vision_service_status: dict[str, Any] = {
            "enabled": bool(self._settings.vision_service_poll_enabled),
            "base_url": self._settings.vision_service_base_url.rstrip("/"),
            "camera_id": self._settings.vision_service_camera_id,
            "poll_hz": self._settings.vision_service_poll_hz,
            "last_poll_at": None,
            "last_ok_at": None,
            "last_error": None,
            "health": None,
            "source": None,
        }

    def ingest(self, payload: VideoAnalysisPushRequest) -> VideoAnalysisIngestResponse:
        record = self._adapter.normalize(payload)
        self._records[(record.camera_id, record.stream_name)] = record
        self._updated_at = record.received_at
        return VideoAnalysisIngestResponse(
            camera_id=record.camera_id,
            stream_name=record.stream_name,
            received_at=record.received_at,
            service_state=record.service_state,
            stale=record.stale,
        )

    def poll_once(self) -> dict[str, Any]:
        """Pull health, stream source, and latest AI result from the vision service."""

        base_url = self._settings.vision_service_base_url.rstrip("/")
        camera_id = (self._settings.vision_service_camera_id or "camera_01").strip() or "camera_01"
        self._vision_service_status.update(
            {
                "enabled": bool(self._settings.vision_service_poll_enabled),
                "base_url": base_url,
                "camera_id": camera_id,
                "poll_hz": self._settings.vision_service_poll_hz,
                "last_poll_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        try:
            health = self._get_json(f"{base_url}/healthz")
            source = self._get_json_or_text(f"{base_url}/stream/source", params={"camera_id": camera_id})
            latest = self._get_json(f"{base_url}/integration/results/{camera_id}/latest")
            payload = self._payload_from_vision_latest(latest, camera_id=camera_id, source=source)
            accepted = self.ingest(VideoAnalysisPushRequest(**payload))
            self._vision_service_status.update(
                {
                    "last_ok_at": datetime.now(timezone.utc).isoformat(),
                    "last_error": None,
                    "health": health,
                    "source": source,
                    "latest_received_at": accepted.received_at.isoformat(),
                }
            )
            return {"ok": True, "accepted": accepted.model_dump(mode="json"), "vision_service": self.vision_service_status()}
        except Exception as exc:
            self._vision_service_status["last_error"] = str(exc)
            LOGGER.warning("Vision service polling failed: %s", exc)
            return {"ok": False, "error": str(exc), "vision_service": self.vision_service_status()}

    def get_vision_health(self) -> Any:
        return self._get_json(f"{self._settings.vision_service_base_url.rstrip('/')}/healthz")

    def get_vision_source(self, camera_id: str | None = None) -> Any:
        resolved_camera_id = (camera_id or self._settings.vision_service_camera_id or "camera_01").strip()
        return self._get_json_or_text(
            f"{self._settings.vision_service_base_url.rstrip('/')}/stream/source",
            params={"camera_id": resolved_camera_id},
        )

    def get_vision_latest(self, camera_id: str | None = None) -> Any:
        resolved_camera_id = (camera_id or self._settings.vision_service_camera_id or "camera_01").strip()
        return self._get_json(
            f"{self._settings.vision_service_base_url.rstrip('/')}/integration/results/{resolved_camera_id}/latest"
        )

    def probe_vision_stream(self, payload: dict[str, Any]) -> Any:
        return self._post_json(f"{self._settings.vision_service_base_url.rstrip('/')}/stream/probe", payload)

    def switch_vision_host(self, payload: dict[str, Any]) -> Any:
        return self._post_json(f"{self._settings.vision_service_base_url.rstrip('/')}/stream/switch-host", payload)

    def vision_service_status(self) -> dict[str, Any]:
        return dict(self._vision_service_status)

    def status(self, *, include_mock: bool = True) -> VideoBridgeStatusResponse:
        records = list(self._records.values())
        if not records and include_mock:
            records = [self._adapter.mock_record()]

        records.sort(key=lambda item: item.received_at, reverse=True)
        latest = records[0] if records else None
        bridge_state = latest.service_state if latest else "unknown"
        if records and any(item.service_state in {"error", "degraded"} for item in records):
            bridge_state = "degraded"

        return VideoBridgeStatusResponse(
            bridge_state=bridge_state,
            adapter_version=ADAPTER_VERSION,
            camera_count=len(records),
            updated_at=self._updated_at,
            latest=latest,
            cameras=records,
            notes=[
                "Main system pulls standalone vision-service telemetry at 1-5Hz.",
                "Vision service owns RTSP and AI inference; this bridge stores latest structured results.",
            ],
            vision_service=self.vision_service_status(),
        )

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(url, params=params, timeout=self._settings.vision_service_timeout_seconds)
        response.raise_for_status()
        return response.json()

    def _get_json_or_text(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(url, params=params, timeout=self._settings.vision_service_timeout_seconds)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type.lower():
            return response.json()
        text = response.text
        parsed: dict[str, str] = {}
        for raw_line in text.splitlines():
            key, separator, value = raw_line.partition(":")
            if separator and key.strip():
                parsed[key.strip()] = value.strip()
        return parsed or text

    def _post_json(self, url: str, payload: dict[str, Any]) -> Any:
        response = self._session.post(url, json=payload, timeout=self._settings.vision_service_timeout_seconds)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type.lower():
            return response.json()
        return response.text

    def _payload_from_vision_latest(self, latest: Any, *, camera_id: str, source: Any) -> dict[str, Any]:
        data = latest if isinstance(latest, dict) else {"raw": latest}
        track = self._select_primary_track(data)
        track_id = self._first_present(track, data, keys=("track_id", "id"))
        bbox = self._coerce_bbox(self._first_present(track, data, keys=("bbox", "box")))
        pose = track.get("pose") if isinstance(track.get("pose"), dict) else data.get("pose")
        keypoints = pose.get("keypoints") if isinstance(pose, dict) else None
        frame_age_ms = self._coerce_int(data.get("frame_age_ms") or data.get("age_ms"))
        display_source = data.get("display_source") or self._source_value(source, "display_source_current")
        analysis_source = data.get("analysis_source") or "analysis"
        is_target = bool(self._first_present(track, data, keys=("is_target", "target_matched")) or False)
        fall_prob = self._coerce_float(
            self._first_present(track, data, keys=("fall_prob", "fall_score", "score", "confidence"))
        )
        fall_state = self._fall_state_from_payload(data, track)

        return {
            "camera_id": str(data.get("camera_id") or camera_id),
            "stream_name": str(analysis_source or "analysis"),
            "service_state": "running",
            "camera_lost": False,
            "capture_stale": bool(frame_age_ms is not None and frame_age_ms >= 3000),
            "frame_age_ms": frame_age_ms,
            "video_fps": self._coerce_float(data.get("video_fps") or data.get("source_fps")),
            "overlay_fps": self._coerce_float(data.get("overlay_fps") or data.get("analysis_fps")),
            "ws_fps": self._coerce_float(data.get("ws_fps")),
            "stream_type": "unknown",
            "stream_url": None,
            "track_id": str(track_id) if track_id is not None else None,
            "bbox": bbox,
            "target": {
                "target_id": str(track_id) if track_id is not None else None,
                "label": "target" if is_target else "person",
                "matched": is_target,
                "confidence": self._coerce_float(self._first_present(track, data, keys=("target_score", "confidence"))),
                "metadata": {"is_target": is_target},
            },
            "fall_state": fall_state,
            "risk": "high" if fall_state in {"confirmed_fall", "fallen"} else "low",
            "fall_prob": fall_prob,
            "snapshot_url": data.get("snapshot_url"),
            "timestamp": self._coerce_timestamp(data.get("timestamp") or data.get("ts")),
            "metadata": {
                "source": "vision_service_pull",
                "display_source": display_source,
                "analysis_source": analysis_source,
                "pose_keypoint_count": len(keypoints) if isinstance(keypoints, list) else 0,
                "pose": pose if isinstance(pose, dict) else None,
                "source_status": source,
                "raw": data,
            },
        }

    @staticmethod
    def _select_primary_track(data: dict[str, Any]) -> dict[str, Any]:
        objects = data.get("objects") or data.get("tracks") or data.get("detections")
        if isinstance(objects, list) and objects:
            target = next((item for item in objects if isinstance(item, dict) and item.get("is_target")), None)
            if isinstance(target, dict):
                return target
            first = objects[0]
            return first if isinstance(first, dict) else {}
        return data

    @staticmethod
    def _first_present(*containers: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for container in containers:
            for key in keys:
                value = container.get(key)
                if value is not None:
                    return value
        return None

    @staticmethod
    def _coerce_bbox(value: Any) -> list[float] | None:
        if not isinstance(value, list) or len(value) < 4:
            return None
        try:
            return [float(item) for item in value[:4]]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            seconds = float(value)
            if seconds > 10_000_000_000:
                seconds = seconds / 1000.0
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _source_value(source: Any, key: str) -> Any:
        if isinstance(source, dict):
            return source.get(key)
        return None

    @staticmethod
    def _fall_state_from_payload(data: dict[str, Any], track: dict[str, Any]) -> str:
        raw = str(data.get("fall_state") or data.get("state") or track.get("fall_state") or track.get("state") or "normal")
        normalized = raw.strip().lower()
        if normalized in {"confirmed_fall", "fallen", "suspected_fall", "recovery", "normal", "error"}:
            return normalized
        if "fall" in normalized:
            return "confirmed_fall"
        return "normal"


LOGGER = logging.getLogger(__name__)
