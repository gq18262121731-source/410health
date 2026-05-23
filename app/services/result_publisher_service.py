from __future__ import annotations

import threading
import time

from app.core.config import Settings
from app.core.logger import get_logger
from app.detection.realtime_result_store import ObjectSnapshot, RealtimeResultStore
from app.monitoring.metrics import FPSMeter
from app.schemas.common import utc_now_iso
from app.schemas.vision_result import DetectedObject, VisionResult
from app.services.temporal_service import TemporalService
from app.streaming.result_channel_manager import ResultChannelManager

logger = get_logger(__name__)


class ResultPublisherService:
    def __init__(
        self,
        settings: Settings,
        realtime_store: RealtimeResultStore,
        result_channels: ResultChannelManager,
        temporal_service: TemporalService | None = None,
    ) -> None:
        self.settings = settings
        self.realtime_store = realtime_store
        self.result_channels = result_channels
        self.temporal_service = temporal_service
        self._workers: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._fps: dict[str, FPSMeter] = {}
        self._last_error: dict[str, str | None] = {}
        self._last_detection_to_publish_lag_ms: dict[str, float | None] = {}
        self._lock = threading.Lock()

    def start_for_camera(self, camera_id: str) -> None:
        with self._lock:
            existing = self._workers.get(camera_id)
            if existing and existing.is_alive():
                return
            stop_event = threading.Event()
            worker = threading.Thread(
                target=self._run_loop,
                args=(camera_id, stop_event),
                name=f"result-publisher-{camera_id}",
                daemon=True,
            )
            self._stops[camera_id] = stop_event
            self._fps[camera_id] = FPSMeter()
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

    def status_fps(self, camera_id: str) -> float:
        with self._lock:
            fps = self._fps.get(camera_id)
        return fps.fps if fps else 0.0

    def detection_to_publish_lag_ms(self, camera_id: str) -> float | None:
        with self._lock:
            return self._last_detection_to_publish_lag_ms.get(camera_id)

    def last_error(self, camera_id: str) -> str | None:
        with self._lock:
            return self._last_error.get(camera_id)

    def _run_loop(self, camera_id: str, stop_event: threading.Event) -> None:
        interval = 1 / max(self.settings.result_publish_fps, 1)
        logger.info("result_publisher_started camera_id=%s", camera_id)
        while not stop_event.is_set():
            try:
                result = self._build_result(camera_id)
                if result is not None:
                    self.realtime_store.update_published(result)
                    self.result_channels.publish(result)
                    with self._lock:
                        self._fps.setdefault(camera_id, FPSMeter()).tick()
                        self._last_error[camera_id] = None
                else:
                    with self._lock:
                        self._last_error[camera_id] = None
            except Exception as exc:
                logger.exception("result_publisher_error camera_id=%s", camera_id)
                with self._lock:
                    self._last_error[camera_id] = str(exc)
            stop_event.wait(interval)
        logger.info("result_publisher_stopped camera_id=%s", camera_id)

    def _build_result(self, camera_id: str) -> VisionResult | None:
        pipeline = self.realtime_store.snapshot(camera_id)
        base = pipeline.latest_tracking or pipeline.latest_detection
        if base is None:
            return None

        objects = base.objects
        if self._is_fresh(pipeline.latest_pose, self.settings.pose_result_ttl_ms):
            objects = self._merge_objects(objects, pipeline.latest_pose)
        if self._is_fresh(pipeline.latest_behavior, self.settings.behavior_result_ttl_ms):
            objects = self._merge_objects(objects, pipeline.latest_behavior)
        if self.temporal_service is not None:
            objects = self.temporal_service.enrich(camera_id=camera_id, objects=objects)

        detection = pipeline.latest_detection
        detector = detection.detector if detection else {}
        if detection is not None:
            lag_ms = round((time.monotonic() - detection.monotonic_at) * 1000, 2)
            with self._lock:
                self._last_detection_to_publish_lag_ms[camera_id] = lag_ms

        return VisionResult(
            camera_id=camera_id,
            timestamp=utc_now_iso(),
            frame_seq=base.frame_seq,
            frame_width=base.frame_width,
            frame_height=base.frame_height,
            objects=objects,
            detector=detector,
        )

    @staticmethod
    def _merge_objects(base_objects: list[DetectedObject], snapshot: ObjectSnapshot) -> list[DetectedObject]:
        by_track = {
            item.track_id: item
            for item in snapshot.objects
            if item.track_id is not None
        }
        merged: list[DetectedObject] = []
        for item in base_objects:
            patch = by_track.get(item.track_id)
            if patch is None:
                merged.append(item)
                continue
            updates = {}
            if patch.pose is not None:
                updates["pose"] = patch.pose
            if patch.behavior is not None:
                updates["behavior"] = patch.behavior
            if patch.person_id is not None:
                updates["person_id"] = patch.person_id
                updates["person_name"] = patch.person_name
                updates["identity_state"] = patch.identity_state
                updates["is_target"] = patch.is_target
            merged.append(item.model_copy(update=updates))
        return merged

    @staticmethod
    def _is_fresh(snapshot: ObjectSnapshot | None, ttl_ms: int) -> bool:
        if snapshot is None:
            return False
        if ttl_ms <= 0:
            return True
        return (time.monotonic() - snapshot.monotonic_at) * 1000 <= ttl_ms
