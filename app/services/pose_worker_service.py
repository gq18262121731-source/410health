from __future__ import annotations

import threading
import time

from app.camera.source_manager import CameraSourceManager
from app.core.config import Settings
from app.core.logger import get_logger
from app.detection.realtime_result_store import ObjectSnapshot, RealtimeResultStore
from app.monitoring.worker_health import WorkerHealthSnapshot, WorkerHealthTracker
from app.services.behavior_service import BehaviorService
from app.services.pose_service import PoseService

logger = get_logger(__name__)


class PoseWorkerService:
    def __init__(
        self,
        settings: Settings,
        source_manager: CameraSourceManager,
        realtime_store: RealtimeResultStore,
        pose_service: PoseService,
        behavior_service: BehaviorService | None = None,
    ) -> None:
        self.settings = settings
        self.source_manager = source_manager
        self.realtime_store = realtime_store
        self.pose_service = pose_service
        self.behavior_service = behavior_service
        self._workers: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._last_error: dict[str, str | None] = {}
        self._health: dict[str, WorkerHealthTracker] = {}
        self._skip_reasons: dict[str, dict[str, int]] = {}
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
                name=f"pose-worker-{camera_id}",
                daemon=True,
            )
            self._stops[camera_id] = stop_event
            self._health.setdefault(camera_id, WorkerHealthTracker()).mark_restart()
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

    def restart_for_camera(self, camera_id: str) -> bool:
        with self._lock:
            stop_event = self._stops.get(camera_id)
            worker = self._workers.get(camera_id)
        if stop_event:
            stop_event.set()
        if worker and worker.is_alive():
            worker.join(timeout=3)
        if worker and worker.is_alive():
            return False
        with self._lock:
            self._stops.pop(camera_id, None)
            self._workers.pop(camera_id, None)
        self.start_for_camera(camera_id)
        return True

    def stop_all(self) -> None:
        for camera_id in list(self._workers.keys()):
            self.stop_for_camera(camera_id)

    def last_error(self, camera_id: str) -> str | None:
        with self._lock:
            return self._last_error.get(camera_id)

    def health(self, camera_id: str) -> WorkerHealthSnapshot:
        with self._lock:
            worker = self._workers.get(camera_id)
            health = self._health.setdefault(camera_id, WorkerHealthTracker())
        return health.snapshot(worker_alive=bool(worker and worker.is_alive()))

    def _run_loop(self, camera_id: str, stop_event: threading.Event) -> None:
        interval = 1 / max(self.settings.pose_worker_fps, 0.1)
        next_tick = time.perf_counter()
        logger.info("pose_worker_started camera_id=%s", camera_id)
        while not stop_event.is_set():
            delay = next_tick - time.perf_counter()
            if delay > 0:
                stop_event.wait(delay)
            tick_started = time.perf_counter()
            try:
                self._tick(camera_id)
                latency_ms = (time.perf_counter() - tick_started) * 1000
                with self._lock:
                    self._last_error[camera_id] = None
                    self._health.setdefault(camera_id, WorkerHealthTracker()).mark_success(latency_ms)
            except Exception as exc:
                logger.exception("pose_worker_error camera_id=%s", camera_id)
                with self._lock:
                    self._last_error[camera_id] = str(exc)
                    self._health.setdefault(camera_id, WorkerHealthTracker()).mark_error(str(exc))
            next_tick += interval
        logger.info("pose_worker_stopped camera_id=%s", camera_id)

    def _tick(self, camera_id: str) -> None:
        tracking = self.realtime_store.latest_tracking(camera_id)
        detection = self.realtime_store.latest_detection(camera_id)
        detection_objects_count = len(detection.objects) if detection is not None else 0
        if tracking is None or not tracking.objects:
            if detection is not None and detection.objects and self.settings.pose_fallback_to_detection:
                fallback_objects = self._fallback_detection_objects(detection.objects)
                self.pose_service.record_detection_fallback_context(camera_id, detection_objects_count)
                if not fallback_objects:
                    self.pose_service.record_skip(camera_id, "low_confidence")
                    return
                buffer = self.source_manager.get_analysis_buffer(camera_id)
                packet = buffer.latest() if buffer else None
                if packet is None:
                    self.pose_service.record_skip(camera_id, "no_frame")
                    return
                objects = self.pose_service.enrich(
                    camera_id=camera_id,
                    frame=packet.frame,
                    objects=fallback_objects,
                )
                if not self._has_pose(objects):
                    return
                self.realtime_store.update_pose(
                    ObjectSnapshot(
                        camera_id=camera_id,
                        frame_seq=packet.seq,
                        frame_width=packet.width,
                        frame_height=packet.height,
                        timestamp=packet.captured_at_iso,
                        monotonic_at=time.monotonic(),
                        objects=objects,
                    )
                )
                return
            self.pose_service.record_context(
                camera_id,
                detection_objects_count=detection_objects_count,
                tracking_objects_count=0,
                target_objects_count=0,
                identity_state=None,
            )
            self.pose_service.record_skip(camera_id, "no_tracking")
            return
        target_objects = [item for item in tracking.objects if item.is_target and item.track_id is not None]
        identity_state = target_objects[0].identity_state if target_objects else None
        self.pose_service.record_context(
            camera_id,
            detection_objects_count=detection_objects_count,
            tracking_objects_count=len(tracking.objects),
            target_objects_count=len(target_objects),
            identity_state=identity_state,
        )
        buffer = self.source_manager.get_analysis_buffer(camera_id)
        packet = buffer.latest() if buffer else None
        if packet is None:
            self.pose_service.record_skip(camera_id, "no_frame")
            return
        objects = self.pose_service.enrich(
            camera_id=camera_id,
            frame=packet.frame,
            objects=tracking.objects,
        )
        if not self._has_pose(objects):
            return
        pose_snapshot = ObjectSnapshot(
            camera_id=tracking.camera_id,
            frame_seq=packet.seq,
            frame_width=packet.width,
            frame_height=packet.height,
            timestamp=packet.captured_at_iso,
            monotonic_at=time.monotonic(),
            objects=objects,
        )
        self.realtime_store.update_pose(pose_snapshot)
        if self.behavior_service is not None:
            behavior_objects = self.behavior_service.enrich(camera_id=camera_id, objects=objects)
            self.realtime_store.update_behavior(
                ObjectSnapshot(
                    camera_id=tracking.camera_id,
                    frame_seq=packet.seq,
                    frame_width=packet.width,
                    frame_height=packet.height,
                    timestamp=packet.captured_at_iso,
                    monotonic_at=time.monotonic(),
                    objects=behavior_objects,
                )
            )

    def _fallback_detection_objects(self, objects):
        candidates = [
            item
            for item in objects
            if item.label == "person" and item.confidence >= self.settings.pose_fallback_min_confidence
        ]
        if not candidates:
            return []
        best = max(
            candidates,
            key=lambda item: max(0.0, item.bbox[2] - item.bbox[0]) * max(0.0, item.bbox[3] - item.bbox[1]),
        )
        return [best.model_copy(update={"identity_state": "fallback_detection"})]

    @staticmethod
    def _has_pose(objects) -> bool:
        return any(item.pose is not None for item in objects)
