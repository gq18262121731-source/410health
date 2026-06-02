from __future__ import annotations

import threading
import time
import math
from collections import defaultdict, deque
from typing import Any

import requests

from app.camera.source_manager import CameraSourceManager
from app.core.config import Settings
from app.core.logger import get_logger
from app.detection.realtime_result_store import RealtimeResultStore
from app.schemas.vision_result import DetectedObject, VisionResult
from app.services.result_publisher_service import ResultPublisherService

logger = get_logger(__name__)


class VideoBridgePostError(RuntimeError):
    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"video bridge fall event post failed: {status_code}")
        self.status_code = status_code
        self.body = body


class VideoBridgePublisherService:
    """Side-channel publisher for the main-system video_bridge endpoint."""

    def __init__(
        self,
        settings: Settings,
        realtime_store: RealtimeResultStore,
        source_manager: CameraSourceManager,
        result_publisher_service: ResultPublisherService,
    ) -> None:
        self.settings = settings
        self.realtime_store = realtime_store
        self.source_manager = source_manager
        self.result_publisher_service = result_publisher_service
        self._workers: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._last_error: dict[str, str | None] = {}
        self._last_success_at: dict[str, str | None] = {}
        self._pose_history: dict[tuple[str, str], deque[dict[str, float]]] = defaultdict(lambda: deque(maxlen=20))
        self._lock = threading.Lock()

    def start_for_camera(self, camera_id: str) -> None:
        if not self.settings.video_bridge_enabled:
            return
        with self._lock:
            existing = self._workers.get(camera_id)
            if existing and existing.is_alive():
                return
            stop_event = threading.Event()
            worker = threading.Thread(
                target=self._run_loop,
                args=(camera_id, stop_event),
                name=f"video-bridge-publisher-{camera_id}",
                daemon=True,
            )
            self._stops[camera_id] = stop_event
            self._workers[camera_id] = worker
            worker.start()

    def stop_for_camera(self, camera_id: str) -> None:
        with self._lock:
            stop_event = self._stops.pop(camera_id, None)
            worker = self._workers.pop(camera_id, None)
        if stop_event:
            stop_event.set()
        if worker and worker.is_alive():
            worker.join(timeout=3)

    def stop_all(self) -> None:
        for camera_id in list(self._workers.keys()):
            self.stop_for_camera(camera_id)

    def last_error(self, camera_id: str) -> str | None:
        with self._lock:
            return self._last_error.get(camera_id)

    def post_fall_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            self.settings.video_bridge_fall_event_url,
            json=payload,
            timeout=max(self.settings.video_bridge_timeout_seconds, 0.1),
        )
        body = self._response_body(response)
        if response.status_code >= 400:
            raise VideoBridgePostError(response.status_code, body)
        logger.info(
            "video_bridge_fall_event_post_ok camera_id=%s incident_id=%s alarm_id=%s",
            payload.get("camera_id"),
            payload.get("incident_id"),
            body.get("alarm_id") if isinstance(body, dict) else None,
        )
        return {
            "status_code": response.status_code,
            "body": body,
        }

    def _run_loop(self, camera_id: str, stop_event: threading.Event) -> None:
        interval = 1 / max(self.settings.video_bridge_fps, 0.1)
        logger.info(
            "video_bridge_publisher_started camera_id=%s url=%s fps=%s",
            camera_id,
            self.settings.video_bridge_url,
            self.settings.video_bridge_fps,
        )
        while not stop_event.is_set():
            try:
                payload = self._build_payload(camera_id)
                self._post_payload(camera_id, payload)
            except Exception as exc:
                message = str(exc)
                with self._lock:
                    self._last_error[camera_id] = message
                logger.warning("video_bridge_publish_failed camera_id=%s error=%s", camera_id, message)
            stop_event.wait(interval)
        logger.info("video_bridge_publisher_stopped camera_id=%s", camera_id)

    def _post_payload(self, camera_id: str, payload: dict[str, Any]) -> None:
        response = requests.post(
            self.settings.video_bridge_url,
            json=payload,
            timeout=max(self.settings.video_bridge_timeout_seconds, 0.1),
        )
        response.raise_for_status()
        with self._lock:
            self._last_error[camera_id] = None
            self._last_success_at[camera_id] = payload["timestamp"]
        logger.info(
            "video_bridge_publish_ok camera_id=%s stream_name=%s state=%s risk=%s",
            payload.get("camera_id"),
            payload.get("stream_name"),
            payload.get("service_state"),
            payload.get("risk"),
        )

    def _build_payload(self, camera_id: str) -> dict[str, Any]:
        result = self.realtime_store.latest_published(camera_id)
        runtime = self.source_manager.get_runtime(camera_id)
        display_source = "single"
        if runtime and runtime.dual_stream_enabled:
            display_source, _ = self.source_manager.display_state(camera_id)

        display_status = None
        analysis_status = None
        if runtime is not None:
            analysis_status = runtime.analysis_worker.status() if runtime.analysis_worker else None
            if display_source == "analysis":
                display_status = analysis_status
            else:
                display_status = runtime.main_worker.status() if runtime.main_worker else analysis_status

        camera_lost = self._camera_lost(runtime)
        capture_stale = self._capture_stale(runtime)
        service_state = self._service_state(camera_lost, capture_stale)
        target = self._select_target(result)
        timestamp = result.timestamp if result is not None else self._utc_now_iso()
        frame_age_ms = self._int_or_none(getattr(display_status, "frame_age_ms", None))
        video_fps = self._float_or_none(getattr(display_status, "capture_fps", None))
        ws_fps = self.result_publisher_service.status_fps(camera_id)
        pose_fall = self._pose_fall_candidate(camera_id, target, timestamp)

        payload = {
            "camera_id": camera_id,
            "stream_name": display_source or "primary",
            "service_state": service_state,
            "camera_lost": camera_lost,
            "capture_stale": capture_stale,
            "frame_age_ms": frame_age_ms,
            "video_fps": video_fps,
            "overlay_fps": None,
            "ws_fps": ws_fps,
            "stream_type": "ws_image",
            "stream_url": "/ws/camera/processed",
            "track_id": str(target.track_id) if target and target.track_id is not None else None,
            "bbox": target.bbox if target else None,
            "target": self._target_payload(target),
            "fall_state": self._map_fall_state(target),
            "risk": self._map_risk(target),
            "fall_prob": self._fall_probability(target),
            "snapshot_url": None,
            "timestamp": timestamp,
            "metadata": {
                "source": "vision_service",
                "display_source": display_source,
                "analysis_source": result.analysis_source if result is not None else None,
                "frame_seq": result.frame_seq if result is not None else None,
                "analysis_frame_width": result.analysis_frame_width if result is not None else None,
                "analysis_frame_height": result.analysis_frame_height if result is not None else None,
                "display_frame_width": result.display_frame_width if result is not None else None,
                "display_frame_height": result.display_frame_height if result is not None else None,
                "result_object_count": len(result.objects) if result is not None else 0,
                "video_fps_kind": "backend_capture_fps",
                "ws_fps_kind": "result_publish_fps",
                "overlay_fps": "unavailable_from_backend",
                "pose_fall_candidate": pose_fall["pose_fall_candidate"],
                "pose_fall_score": pose_fall["pose_fall_score"],
                "pose_posture_label": pose_fall["pose_posture_label"],
                "pose_reason": pose_fall["pose_reason"],
                "pose_features": pose_fall["pose_features"],
                "detection_to_publish_lag_ms": (
                    self.result_publisher_service.detection_to_publish_lag_ms(camera_id)
                ),
                "analysis_capture_fps": self._float_or_none(getattr(analysis_status, "capture_fps", None)),
                "analysis_frame_age_ms": self._int_or_none(getattr(analysis_status, "frame_age_ms", None)),
                "display_stream_state": getattr(display_status, "stream_state", None),
                "analysis_stream_state": getattr(analysis_status, "stream_state", None),
            },
        }
        return payload

    def _pose_fall_candidate(
        self,
        camera_id: str,
        target: DetectedObject | None,
        timestamp: str,
    ) -> dict[str, Any]:
        if target is None:
            return self._pose_candidate_payload(False, 0.0, "unknown", "no_target", {})

        features = self._pose_features(target, camera_id, timestamp)
        if not features:
            return self._pose_candidate_payload(False, 0.0, "unknown", "missing_bbox_or_pose", {})

        score = 0.0
        reasons = []
        posture = "standing"

        aspect = features.get("bbox_aspect_ratio")
        torso_angle = features.get("torso_angle_deg")
        head_rel_y = features.get("head_relative_y")
        hip_rel_y = features.get("hip_relative_y")
        center_down_speed = features.get("center_down_speed_px_s")
        low_duration_ms = features.get("low_posture_duration_ms")

        if aspect is not None and aspect >= 0.95:
            score += 0.28
            reasons.append(f"wide_bbox:{aspect:.2f}")
            posture = "lying"
        elif aspect is not None and aspect >= 0.65:
            score += 0.12
            reasons.append(f"low_aspect:{aspect:.2f}")
            posture = "sitting"

        if torso_angle is not None and torso_angle >= 60:
            score += 0.26
            reasons.append(f"torso_tilt:{torso_angle:.1f}")
            posture = "lying"
        elif torso_angle is not None and torso_angle >= 38:
            score += 0.12
            reasons.append(f"torso_lean:{torso_angle:.1f}")
            if posture == "standing":
                posture = "sitting"

        if head_rel_y is not None and hip_rel_y is not None and head_rel_y > 0.35 and hip_rel_y > 0.42:
            score += 0.18
            reasons.append(f"low_head_hip:{head_rel_y:.2f}/{hip_rel_y:.2f}")

        if center_down_speed is not None and center_down_speed >= 180:
            score += 0.18
            reasons.append(f"center_down:{center_down_speed:.1f}")

        if low_duration_ms is not None and low_duration_ms >= 900:
            score += 0.18
            reasons.append(f"low_duration:{low_duration_ms:.0f}ms")

        score = round(min(score, 1.0), 3)
        candidate = score >= 0.50 and posture in {"lying", "sitting"}
        if not reasons:
            reasons.append("upright_or_insufficient_motion")
        return self._pose_candidate_payload(candidate, score, posture, ",".join(reasons), features)

    def _pose_features(self, target: DetectedObject, camera_id: str, timestamp: str) -> dict[str, float] | None:
        bbox = self._bbox_values(target.bbox)
        if bbox is None:
            return None
        x1, y1, x2, y2 = bbox
        width = max(0.0, x2 - x1)
        height = max(0.0, y2 - y1)
        if width <= 0 or height <= 0:
            return None

        keypoints = self._keypoints_by_name(target.pose)
        head = self._mean_point(keypoints, ["nose", "left_eye", "right_eye", "left_ear", "right_ear"])
        shoulder = self._mean_point(keypoints, ["left_shoulder", "right_shoulder"])
        hip = self._mean_point(keypoints, ["left_hip", "right_hip"])
        torso_angle = self._torso_angle_deg(shoulder, hip)
        center_y = (y1 + y2) / 2
        now = self._parse_timestamp_seconds(timestamp)
        track_key = str(target.track_id) if target.track_id is not None else "untracked"
        history_key = (camera_id, track_key)
        history = self._pose_history[history_key]
        center_down_speed = self._center_down_speed(history, now, center_y)

        low_posture = (width / height) >= 0.65 or (torso_angle is not None and torso_angle >= 38)
        history.append({"at": now, "center_y": center_y, "low": 1.0 if low_posture else 0.0})
        low_duration_ms = self._low_posture_duration_ms(history, now)

        return {
            "bbox_aspect_ratio": round(width / height, 4),
            "bbox_center_y": round(center_y, 2),
            "torso_angle_deg": round(torso_angle, 2) if torso_angle is not None else None,
            "head_relative_y": self._relative_y(head, y1, height),
            "shoulder_relative_y": self._relative_y(shoulder, y1, height),
            "hip_relative_y": self._relative_y(hip, y1, height),
            "center_down_speed_px_s": round(center_down_speed, 2) if center_down_speed is not None else None,
            "low_posture_duration_ms": round(low_duration_ms, 2),
        }

    @staticmethod
    def _pose_candidate_payload(
        candidate: bool,
        score: float,
        posture: str,
        reason: str,
        features: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "pose_fall_candidate": candidate,
            "pose_fall_score": score,
            "pose_posture_label": posture,
            "pose_reason": reason,
            "pose_features": features,
        }

    @staticmethod
    def _bbox_values(bbox: list[float] | None) -> tuple[float, float, float, float] | None:
        if not isinstance(bbox, list) or len(bbox) < 4:
            return None
        try:
            values = tuple(float(value) for value in bbox[:4])
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in values):
            return None
        return values

    @staticmethod
    def _keypoints_by_name(pose: dict | None) -> dict[str, dict[str, float]]:
        if not isinstance(pose, dict):
            return {}
        keypoints = {}
        for item in pose.get("keypoints") or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            try:
                x = float(item.get("x"))
                y = float(item.get("y"))
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                continue
            if name and confidence >= 0.2 and math.isfinite(x) and math.isfinite(y):
                keypoints[str(name)] = {"x": x, "y": y, "confidence": confidence}
        return keypoints

    @staticmethod
    def _mean_point(keypoints: dict[str, dict[str, float]], names: list[str]) -> tuple[float, float] | None:
        points = [keypoints[name] for name in names if name in keypoints]
        if not points:
            return None
        return (
            sum(point["x"] for point in points) / len(points),
            sum(point["y"] for point in points) / len(points),
        )

    @staticmethod
    def _torso_angle_deg(
        shoulder: tuple[float, float] | None,
        hip: tuple[float, float] | None,
    ) -> float | None:
        if shoulder is None or hip is None:
            return None
        dx = hip[0] - shoulder[0]
        dy = hip[1] - shoulder[1]
        if dx == 0 and dy == 0:
            return None
        return abs(math.degrees(math.atan2(dx, dy)))

    @staticmethod
    def _relative_y(point: tuple[float, float] | None, bbox_y: float, bbox_height: float) -> float | None:
        if point is None or bbox_height <= 0:
            return None
        return round((point[1] - bbox_y) / bbox_height, 4)

    @staticmethod
    def _parse_timestamp_seconds(timestamp: str) -> float:
        from datetime import datetime

        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return time.time()

    @staticmethod
    def _center_down_speed(
        history: deque[dict[str, float]],
        now: float,
        center_y: float,
    ) -> float | None:
        candidates = [item for item in history if now - item["at"] <= 1.2]
        if not candidates:
            return None
        previous = candidates[0]
        elapsed = now - previous["at"]
        if elapsed <= 0.05:
            return None
        return max(0.0, (center_y - previous["center_y"]) / elapsed)

    @staticmethod
    def _low_posture_duration_ms(history: deque[dict[str, float]], now: float) -> float:
        started_at = None
        for item in reversed(history):
            if item.get("low") != 1.0:
                break
            started_at = item["at"]
        if started_at is None:
            return 0.0
        return max(0.0, (now - started_at) * 1000)

    @staticmethod
    def _select_target(result: VisionResult | None) -> DetectedObject | None:
        if result is None or not result.objects:
            return None
        targets = [item for item in result.objects if item.is_target]
        if targets:
            return targets[0]
        tracked = [item for item in result.objects if item.track_id is not None]
        if tracked:
            return tracked[0]
        return result.objects[0]

    @staticmethod
    def _target_payload(target: DetectedObject | None) -> dict[str, Any] | None:
        if target is None:
            return None
        return {
            "target_id": str(target.track_id) if target.track_id is not None else target.person_id,
            "label": target.person_name or target.label,
            "matched": bool(target.person_id),
            "confidence": target.confidence,
            "metadata": {
                "person_id": target.person_id,
                "person_name": target.person_name,
                "identity_state": target.identity_state,
                "is_target": target.is_target,
            },
        }

    @staticmethod
    def _map_fall_state(target: DetectedObject | None) -> str:
        raw = None
        if target is not None and target.fall_decision:
            raw = target.fall_decision.get("fall_state")
        mapping = {
            "normal": "normal",
            "unstable": "suspected_fall",
            "falling": "suspected_fall",
            "fallen_candidate": "fallen",
            "fallen_confirmed": "confirmed_fall",
            "cooldown": "recovery",
        }
        return mapping.get(str(raw or "normal"), "unknown")

    @staticmethod
    def _map_risk(target: DetectedObject | None) -> str:
        raw = None
        if target is not None:
            if target.alarm_preview:
                raw = target.alarm_preview.get("risk_level")
            if raw is None and target.fall_decision:
                raw = target.fall_decision.get("risk_level")
        allowed = {"unknown", "low", "medium", "high", "critical"}
        risk = str(raw or "low")
        return risk if risk in allowed else "unknown"

    @staticmethod
    def _fall_probability(target: DetectedObject | None) -> float | None:
        if target is None or not target.temporal:
            return None
        value = target.temporal.get("fall_probability")
        try:
            if value is None:
                return None
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _camera_lost(runtime) -> bool:
        statuses = []
        if runtime is not None:
            if runtime.main_worker:
                statuses.append(runtime.main_worker.status())
            if runtime.analysis_worker:
                statuses.append(runtime.analysis_worker.status())
        enabled = [status for status in statuses if getattr(status, "running", False)]
        if not enabled:
            return True
        return not any(getattr(status, "connected", False) for status in enabled)

    @staticmethod
    def _capture_stale(runtime) -> bool:
        if runtime is None:
            return True
        workers = [worker for worker in (runtime.main_worker, runtime.analysis_worker) if worker is not None]
        if not workers:
            return True
        for worker in workers:
            status = worker.status()
            age_ms = getattr(status, "frame_age_ms", None)
            if getattr(status, "connected", False) and age_ms is not None and age_ms <= 3000:
                return False
        return True

    @staticmethod
    def _service_state(camera_lost: bool, capture_stale: bool) -> str:
        if camera_lost:
            return "error"
        if capture_stale:
            return "degraded"
        return "running"

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return max(0, int(round(float(value))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try:
            if value is None:
                return None
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _utc_now_iso() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _response_body(response: requests.Response) -> dict[str, Any] | list[Any] | str | None:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text
