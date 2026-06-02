from __future__ import annotations

import threading
import time

from app.core.config import Settings
from app.core.logger import get_logger
from app.detection.realtime_result_store import DetectionSnapshot, ObjectSnapshot, RealtimeResultStore
from app.monitoring.metrics import FPSMeter
from app.monitoring.worker_health import WorkerHealthSnapshot, WorkerHealthTracker
from app.schemas.vision_result import DetectedObject
from app.services.identity_binding_service import IdentityBindingService
from app.services.tracking_service import TrackingService

logger = get_logger(__name__)


class TrackingWorkerService:
    def __init__(
        self,
        settings: Settings,
        realtime_store: RealtimeResultStore,
        tracking_service: TrackingService,
        identity_binding_service: IdentityBindingService | None = None,
    ) -> None:
        self.settings = settings
        self.realtime_store = realtime_store
        self.tracking_service = tracking_service
        self.identity_binding_service = identity_binding_service
        self._workers: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._fps: dict[str, FPSMeter] = {}
        self._last_error: dict[str, str | None] = {}
        self._last_detection_seq: dict[str, int] = {}
        self._last_tracking_snapshot: dict[str, ObjectSnapshot] = {}
        self._health: dict[str, WorkerHealthTracker] = {}
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
                name=f"tracking-worker-{camera_id}",
                daemon=True,
            )
            self._stops[camera_id] = stop_event
            self._fps[camera_id] = FPSMeter()
            self._health.setdefault(camera_id, WorkerHealthTracker()).mark_restart()
            self._workers[camera_id] = worker
            worker.start()

    def stop_for_camera(self, camera_id: str) -> None:
        with self._lock:
            stop_event = self._stops.pop(camera_id, None)
            worker = self._workers.pop(camera_id, None)
            self._last_detection_seq.pop(camera_id, None)
            self._last_tracking_snapshot.pop(camera_id, None)
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

    def last_error(self, camera_id: str) -> str | None:
        with self._lock:
            return self._last_error.get(camera_id)

    def health(self, camera_id: str) -> WorkerHealthSnapshot:
        with self._lock:
            worker = self._workers.get(camera_id)
            health = self._health.setdefault(camera_id, WorkerHealthTracker())
        return health.snapshot(worker_alive=bool(worker and worker.is_alive()))

    def _run_loop(self, camera_id: str, stop_event: threading.Event) -> None:
        interval = 1 / max(self.settings.tracking_worker_fps, 1)
        logger.info("tracking_worker_started camera_id=%s", camera_id)
        while not stop_event.is_set():
            tick_started = time.perf_counter()
            try:
                self._tick(camera_id)
                latency_ms = (time.perf_counter() - tick_started) * 1000
                with self._lock:
                    self._fps.setdefault(camera_id, FPSMeter()).tick()
                    self._last_error[camera_id] = None
                    self._health.setdefault(camera_id, WorkerHealthTracker()).mark_success(latency_ms)
            except Exception as exc:
                logger.exception("tracking_worker_error camera_id=%s", camera_id)
                with self._lock:
                    self._last_error[camera_id] = str(exc)
                    self._health.setdefault(camera_id, WorkerHealthTracker()).mark_error(str(exc))
            stop_event.wait(interval)
        logger.info("tracking_worker_stopped camera_id=%s", camera_id)

    def _tick(self, camera_id: str) -> None:
        detection = self.realtime_store.latest_detection(camera_id)
        if detection is None:
            return
        with self._lock:
            last_seq = self._last_detection_seq.get(camera_id)
        if detection.frame_seq != last_seq:
            objects = self._update_from_detection(detection)
            with self._lock:
                self._last_detection_seq[camera_id] = detection.frame_seq
        else:
            objects = self._hold_or_predict(camera_id)
            if objects is None:
                return

        snapshot = ObjectSnapshot(
            camera_id=detection.camera_id,
            frame_seq=detection.frame_seq,
            frame_width=detection.frame_width,
            frame_height=detection.frame_height,
            timestamp=detection.timestamp,
            monotonic_at=time.monotonic(),
            objects=objects,
        )
        self.realtime_store.update_tracking(snapshot)
        with self._lock:
            self._last_tracking_snapshot[camera_id] = snapshot

    def _update_from_detection(self, detection: DetectionSnapshot) -> list[DetectedObject]:
        objects = self.tracking_service.enrich(
            camera_id=detection.camera_id,
            detections=detection.objects,
            frame=detection.frame,
        )
        if self.identity_binding_service is not None:
            objects = self.identity_binding_service.apply_cached(detection.camera_id, objects)
        return objects

    def _hold_or_predict(self, camera_id: str) -> list[DetectedObject] | None:
        with self._lock:
            previous = self._last_tracking_snapshot.get(camera_id)
        if previous is None:
            return None
        # Phase 4.2 minimum: keep the latest tracked boxes alive between detector updates.
        return previous.objects
