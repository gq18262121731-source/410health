from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import numpy as np

from app.ai.inference_guard import ultralytics_inference_lock
from app.core.config import Settings
from app.core.logger import get_logger
from app.monitoring.metrics import FPSMeter
from app.pose.mock_pose_estimator import MockPoseEstimator
from app.pose.pose_estimator import PoseEstimator
from app.pose.schemas import PoseStatus
from app.pose.yolo_pose_estimator import YoloPoseEstimator
from app.schemas.vision_result import DetectedObject

logger = get_logger(__name__)


class PoseService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._estimator: PoseEstimator | None = None
        self._fps: dict[str, FPSMeter] = {}
        self._last_run_at: dict[str, float] = {}
        self._last_error: dict[str, str | None] = {}
        self._last_inference_latency_ms: dict[str, float | None] = {}
        self._slow_inference_count: dict[str, int] = {}
        self._skipped_due_to_busy: dict[str, int] = {}
        self._circuit_open_until: dict[str, float] = {}
        self._last_lock_wait_ms: dict[str, float | None] = {}
        self._lock_wait_values_ms: dict[str, list[float]] = {}
        self._pose_attempts: dict[str, int] = {}
        self._pose_success: dict[str, int] = {}
        self._skip_reasons: dict[str, dict[str, int]] = {}
        self._detection_objects_count: dict[str, int] = {}
        self._tracking_objects_count: dict[str, int] = {}
        self._target_objects_count: dict[str, int] = {}
        self._last_identity_state: dict[str, str | None] = {}
        self._pose_target_source: dict[str, str] = {}
        self._fallback_used_count: dict[str, int] = {}
        self._last_fallback_reason: dict[str, str | None] = {}
        self._pose_objects_count: dict[str, int] = {}
        self._pose_result_writeback_ok: dict[str, bool] = {}
        self._last_target_track_id: dict[str, int | None] = {}
        self._last_target_confidence: dict[str, float | None] = {}
        self._last_bbox: dict[str, list[float] | None] = {}
        self._last_pose_started_at: dict[str, str | None] = {}
        self._last_pose_completed_at: dict[str, str | None] = {}
        self._last_pose_error: dict[str, str | None] = {}
        self._lock = threading.Lock()

    def enrich(
        self,
        camera_id: str,
        frame: np.ndarray,
        objects: list[DetectedObject],
    ) -> list[DetectedObject]:
        if not self.settings.enable_pose:
            return objects
        if not self._should_run(camera_id):
            return objects
        if self._is_circuit_open(camera_id):
            self._record_skip(camera_id, "circuit_open")
            return objects

        try:
            estimator = self._get_estimator()
            self._record_attempt(camera_id)
            target_objects, target_reason, target_source = self._select_pose_targets(camera_id, objects)
            if not target_objects:
                self._set_target_source(camera_id, "none")
                self._record_skip(camera_id, target_reason or "no_target_object")
                return objects
            target = target_objects[0]
            if not self._has_valid_bbox(target.bbox):
                self._set_target_source(camera_id, target_source)
                self._record_skip(camera_id, "no_bbox")
                return objects
            self._record_target(camera_id, target)
            self._set_target_source(camera_id, target_source)
            lock_blocking = not self.settings.pose_skip_when_inference_busy
            with ultralytics_inference_lock(blocking=lock_blocking) as lock_state:
                acquired, wait_ms = lock_state
                if not acquired:
                    with self._lock:
                        self._skipped_due_to_busy[camera_id] = self._skipped_due_to_busy.get(camera_id, 0) + 1
                        self._last_lock_wait_ms[camera_id] = round(wait_ms, 2)
                        self._last_run_at[camera_id] = time.monotonic()
                    self._record_skip(camera_id, "inference_lock_busy")
                    return objects
                self._record_lock_wait(camera_id, wait_ms)
                self._last_pose_started_at[camera_id] = utc_now_iso()
                started_at = time.monotonic()
                pose_by_track = estimator.estimate(frame, target_objects)
                latency_ms = (time.monotonic() - started_at) * 1000
            self._last_pose_completed_at[camera_id] = utc_now_iso()
            if not pose_by_track:
                self._record_skip(camera_id, "low_confidence")
                return objects
            self._record_latency(camera_id, latency_ms)
            enriched: list[DetectedObject] = []
            pose_objects_count = 0
            for item in objects:
                pose = pose_by_track.get(item.track_id) if item.track_id is not None else None
                if pose is not None:
                    pose_objects_count += 1
                enriched.append(item.model_copy(update={"pose": pose.model_dump() if pose else None}))
            with self._lock:
                self._fps.setdefault(camera_id, FPSMeter()).tick()
                self._last_error[camera_id] = None
                self._last_pose_error[camera_id] = None
                self._pose_success[camera_id] = self._pose_success.get(camera_id, 0) + 1
                self._pose_objects_count[camera_id] = pose_objects_count
                self._pose_result_writeback_ok[camera_id] = pose_objects_count > 0
                self._last_run_at[camera_id] = time.monotonic()
            return enriched
        except Exception as exc:
            logger.exception("pose_enrich_failed camera_id=%s", camera_id)
            with self._lock:
                self._last_error[camera_id] = str(exc)
                self._last_pose_error[camera_id] = str(exc)
                self._pose_result_writeback_ok[camera_id] = False
                self._last_pose_completed_at[camera_id] = utc_now_iso()
            self._record_skip(camera_id, "exception")
            return objects

    def status(self, camera_id: str | None = None) -> PoseStatus:
        with self._lock:
            fps = self._fps.get(camera_id or "")
            last_error = self._last_error.get(camera_id or "")
            latency_ms = self._last_inference_latency_ms.get(camera_id or "")
            slow_count = self._slow_inference_count.get(camera_id or "", 0)
            skipped = self._skipped_due_to_busy.get(camera_id or "", 0)
            open_until = self._circuit_open_until.get(camera_id or "", 0.0)
            last_lock_wait_ms = self._last_lock_wait_ms.get(camera_id or "")
            wait_values = list(self._lock_wait_values_ms.get(camera_id or "", []))
            pose_attempts = self._pose_attempts.get(camera_id or "", 0)
            pose_success = self._pose_success.get(camera_id or "", 0)
            skip_reasons = dict(self._skip_reasons.get(camera_id or "", {}))
            detection_objects_count = self._detection_objects_count.get(camera_id or "", 0)
            tracking_objects_count = self._tracking_objects_count.get(camera_id or "", 0)
            target_objects_count = self._target_objects_count.get(camera_id or "", 0)
            last_identity_state = self._last_identity_state.get(camera_id or "")
            pose_target_source = self._pose_target_source.get(camera_id or "", "none")
            fallback_used_count = self._fallback_used_count.get(camera_id or "", 0)
            last_fallback_reason = self._last_fallback_reason.get(camera_id or "")
            pose_objects_count = self._pose_objects_count.get(camera_id or "", 0)
            pose_result_writeback_ok = self._pose_result_writeback_ok.get(camera_id or "", False)
            last_target_track_id = self._last_target_track_id.get(camera_id or "")
            last_target_confidence = self._last_target_confidence.get(camera_id or "")
            last_bbox = self._last_bbox.get(camera_id or "")
            last_pose_started_at = self._last_pose_started_at.get(camera_id or "")
            last_pose_completed_at = self._last_pose_completed_at.get(camera_id or "")
            last_pose_error = self._last_pose_error.get(camera_id or "")
            remaining_ms = max(0.0, (open_until - time.monotonic()) * 1000) if open_until else None
        avg_wait_ms = round(sum(wait_values) / len(wait_values), 2) if wait_values else None
        p95_wait_ms = round(sorted(wait_values)[int(round((len(wait_values) - 1) * 0.95))], 2) if wait_values else None
        return PoseStatus(
            pose_enabled=self.settings.enable_pose,
            pose_provider=self.settings.pose_provider,
            pose_fps=fps.fps if fps else 0.0,
            pose_attempts=pose_attempts,
            pose_success=pose_success,
            detection_objects_count=detection_objects_count,
            tracking_objects_count=tracking_objects_count,
            target_objects_count=target_objects_count,
            last_identity_state=last_identity_state,
            pose_target_source=pose_target_source,
            fallback_used_count=fallback_used_count,
            last_fallback_reason=last_fallback_reason,
            pose_objects_count=pose_objects_count,
            pose_result_writeback_ok=pose_result_writeback_ok,
            last_inference_latency_ms=latency_ms,
            lock_wait_avg_ms=avg_wait_ms,
            lock_wait_p95_ms=p95_wait_ms,
            last_lock_wait_ms=last_lock_wait_ms,
            slow_inference_count=slow_count,
            skipped_due_to_busy=skipped,
            pose_skip_reasons=skip_reasons,
            last_target_track_id=last_target_track_id,
            last_target_confidence=last_target_confidence,
            last_bbox=last_bbox,
            last_pose_error=last_pose_error,
            last_pose_started_at=last_pose_started_at,
            last_pose_completed_at=last_pose_completed_at,
            circuit_open=bool(remaining_ms and remaining_ms > 0),
            circuit_cooldown_remaining_ms=remaining_ms,
            last_error=last_error,
        )

    def _should_run(self, camera_id: str) -> bool:
        if self.settings.pose_fps <= 0:
            return False
        now = time.monotonic()
        min_interval = 1 / self.settings.pose_fps
        with self._lock:
            last_run_at = self._last_run_at.get(camera_id)
        return last_run_at is None or now - last_run_at >= min_interval

    def _is_circuit_open(self, camera_id: str) -> bool:
        now = time.monotonic()
        with self._lock:
            open_until = self._circuit_open_until.get(camera_id, 0.0)
            if open_until and now < open_until:
                self._last_run_at[camera_id] = now
                return True
            if open_until:
                self._circuit_open_until.pop(camera_id, None)
                self._slow_inference_count[camera_id] = 0
        return False

    def _record_latency(self, camera_id: str, latency_ms: float) -> None:
        max_ms = self.settings.pose_max_inference_ms
        with self._lock:
            self._last_inference_latency_ms[camera_id] = round(latency_ms, 2)
            if max_ms > 0 and latency_ms > max_ms:
                slow_count = self._slow_inference_count.get(camera_id, 0) + 1
                self._slow_inference_count[camera_id] = slow_count
                if slow_count >= self.settings.pose_slow_inference_circuit_breaker_count:
                    cooldown = self.settings.pose_circuit_breaker_cooldown_ms / 1000
                    self._circuit_open_until[camera_id] = time.monotonic() + cooldown
                    self._last_error[camera_id] = (
                        f"pose inference circuit open after {slow_count} slow runs "
                        f"(last={latency_ms:.0f}ms)"
                    )
            else:
                self._slow_inference_count[camera_id] = 0

    def _record_lock_wait(self, camera_id: str, wait_ms: float) -> None:
        rounded = round(wait_ms, 2)
        with self._lock:
            self._last_lock_wait_ms[camera_id] = rounded
            values = self._lock_wait_values_ms.setdefault(camera_id, [])
            values.append(rounded)
            if len(values) > 120:
                self._lock_wait_values_ms[camera_id] = values[-120:]

    def _get_estimator(self) -> PoseEstimator:
        if self._estimator is not None:
            return self._estimator
        provider = self.settings.pose_provider.lower()
        if provider == "mock":
            self._estimator = MockPoseEstimator()
        elif provider in {"yolo", "yolo_pose", "ultralytics"}:
            self._estimator = YoloPoseEstimator(self.settings)
        else:
            raise RuntimeError(f"unsupported pose provider: {self.settings.pose_provider}")
        return self._estimator

    @staticmethod
    def _area(item: DetectedObject) -> float:
        x1, y1, x2, y2 = item.bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    def _select_pose_targets(
        self,
        camera_id: str,
        objects: list[DetectedObject],
    ) -> tuple[list[DetectedObject], str | None, str]:
        targets = [item for item in objects if item.is_target and item.track_id is not None]
        if targets:
            return targets[:1], None, "target"
        candidates = [item for item in objects if item.track_id is not None]
        if candidates and self.settings.pose_fallback_to_largest_track:
            valid = [item for item in candidates if item.confidence >= self.settings.pose_fallback_min_confidence]
            if valid:
                return [max(valid, key=PoseService._area)], None, "largest_track"
            return [], "low_confidence", "none"
        if self.settings.pose_target_only:
            tracked = [item for item in objects if item.track_id is not None]
            if tracked and self.settings.enable_identity_binding and all(item.person_id is None for item in tracked):
                return [], "identity_not_matched", "none"
            if tracked:
                return [], "target_not_locked", "none"
            return [], "no_target_object", "none"
        if not candidates:
            return [], "no_target_object", "none"
        return [max(candidates, key=PoseService._area)], None, "largest_track"

    @staticmethod
    def _has_valid_bbox(bbox: list[float] | None) -> bool:
        if not isinstance(bbox, list) or len(bbox) < 4:
            return False
        x1, y1, x2, y2 = bbox[:4]
        return float(x2) > float(x1) and float(y2) > float(y1)

    def _record_attempt(self, camera_id: str) -> None:
        with self._lock:
            self._pose_attempts[camera_id] = self._pose_attempts.get(camera_id, 0) + 1

    def _record_skip(self, camera_id: str, reason: str) -> None:
        with self._lock:
            reasons = self._skip_reasons.setdefault(camera_id, {})
            reasons[reason] = reasons.get(reason, 0) + 1

    def _record_target(self, camera_id: str, item: DetectedObject) -> None:
        with self._lock:
            self._last_target_track_id[camera_id] = item.track_id
            self._last_target_confidence[camera_id] = round(float(item.confidence), 4)
            self._last_bbox[camera_id] = [round(float(value), 2) for value in item.bbox]
            self._last_identity_state[camera_id] = item.identity_state

    def record_context(
        self,
        camera_id: str,
        *,
        detection_objects_count: int,
        tracking_objects_count: int,
        target_objects_count: int,
        identity_state: str | None,
    ) -> None:
        with self._lock:
            self._detection_objects_count[camera_id] = detection_objects_count
            self._tracking_objects_count[camera_id] = tracking_objects_count
            self._target_objects_count[camera_id] = target_objects_count
            self._last_identity_state[camera_id] = identity_state

    def record_skip(self, camera_id: str, reason: str) -> None:
        self._record_skip(camera_id, reason)

    def record_detection_fallback_context(self, camera_id: str, detection_objects_count: int) -> None:
        with self._lock:
            self._detection_objects_count[camera_id] = detection_objects_count

    def _set_target_source(self, camera_id: str, source: str) -> None:
        with self._lock:
            self._pose_target_source[camera_id] = source
            if source in {"largest_track", "detection"}:
                self._fallback_used_count[camera_id] = self._fallback_used_count.get(camera_id, 0) + 1
                self._last_fallback_reason[camera_id] = source


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
