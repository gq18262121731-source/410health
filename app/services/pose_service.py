from __future__ import annotations

import threading
import time

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
            return objects

        try:
            estimator = self._get_estimator()
            target_objects = self._select_pose_targets(objects)
            if not target_objects:
                return objects
            lock_blocking = not self.settings.pose_skip_when_inference_busy
            with ultralytics_inference_lock(blocking=lock_blocking) as acquired:
                if not acquired:
                    with self._lock:
                        self._skipped_due_to_busy[camera_id] = self._skipped_due_to_busy.get(camera_id, 0) + 1
                        self._last_run_at[camera_id] = time.monotonic()
                    return objects
                started_at = time.monotonic()
                pose_by_track = estimator.estimate(frame, target_objects)
                latency_ms = (time.monotonic() - started_at) * 1000
            self._record_latency(camera_id, latency_ms)
            enriched: list[DetectedObject] = []
            for item in objects:
                pose = pose_by_track.get(item.track_id) if item.track_id is not None else None
                enriched.append(item.model_copy(update={"pose": pose.model_dump() if pose else None}))
            with self._lock:
                self._fps.setdefault(camera_id, FPSMeter()).tick()
                self._last_error[camera_id] = None
                self._last_run_at[camera_id] = time.monotonic()
            return enriched
        except Exception as exc:
            logger.exception("pose_enrich_failed camera_id=%s", camera_id)
            with self._lock:
                self._last_error[camera_id] = str(exc)
            return objects

    def status(self, camera_id: str | None = None) -> PoseStatus:
        with self._lock:
            fps = self._fps.get(camera_id or "")
            last_error = self._last_error.get(camera_id or "")
            latency_ms = self._last_inference_latency_ms.get(camera_id or "")
            slow_count = self._slow_inference_count.get(camera_id or "", 0)
            skipped = self._skipped_due_to_busy.get(camera_id or "", 0)
            open_until = self._circuit_open_until.get(camera_id or "", 0.0)
            remaining_ms = max(0.0, (open_until - time.monotonic()) * 1000) if open_until else None
        return PoseStatus(
            pose_enabled=self.settings.enable_pose,
            pose_provider=self.settings.pose_provider,
            pose_fps=fps.fps if fps else 0.0,
            last_inference_latency_ms=latency_ms,
            slow_inference_count=slow_count,
            skipped_due_to_busy=skipped,
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
    def _select_pose_targets(objects: list[DetectedObject]) -> list[DetectedObject]:
        targets = [item for item in objects if item.is_target and item.track_id is not None]
        if targets:
            return targets[:1]
        candidates = [item for item in objects if item.track_id is not None]
        if not candidates:
            return []
        return [max(candidates, key=PoseService._area)]

    @staticmethod
    def _area(item: DetectedObject) -> float:
        x1, y1, x2, y2 = item.bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)
