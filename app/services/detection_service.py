from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.camera.frame_buffer import FrameBuffer
from app.camera.source_manager import CameraSourceManager
from app.core.config import Settings
from app.core.logger import get_logger
from app.detection.object_detector import DetectionRunStats, PersonDetector, YoloPersonDetector
from app.detection.realtime_result_store import DetectionSnapshot, RealtimeResultStore
from app.monitoring.metrics import FPSMeter
from app.monitoring.worker_health import WorkerHealthSnapshot, WorkerHealthTracker
from app.schemas.common import utc_now_iso

logger = get_logger(__name__)


@dataclass
class DetectionWorkerStatus:
    camera_id: str
    running: bool
    enabled: bool
    loaded: bool
    model_name: str | None
    detection_fps: float = 0.0
    inference_latency_ms: float | None = None
    loop_latency_ms: float | None = None
    lock_wait_avg_ms: float | None = None
    lock_wait_p95_ms: float | None = None
    last_lock_wait_ms: float | None = None
    last_error: str | None = None
    health: WorkerHealthSnapshot | None = None


class DetectionService:
    def __init__(
        self,
        settings: Settings,
        source_manager: CameraSourceManager,
        realtime_store: RealtimeResultStore,
    ) -> None:
        self.settings = settings
        self.source_manager = source_manager
        self.realtime_store = realtime_store
        self.detector: PersonDetector = YoloPersonDetector(settings)
        self._workers: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._fps: dict[str, FPSMeter] = {}
        self._stats: dict[str, DetectionRunStats] = {}
        self._health: dict[str, WorkerHealthTracker] = {}
        self._lock = threading.Lock()

    def start_for_camera(self, camera_id: str) -> None:
        with self._lock:
            existing = self._workers.get(camera_id)
            if existing and existing.is_alive():
                return
            stop_event = threading.Event()
            self._stops[camera_id] = stop_event
            self._fps[camera_id] = FPSMeter()
            self._stats[camera_id] = DetectionRunStats()
            health = self._health.setdefault(camera_id, WorkerHealthTracker())
            health.mark_restart()
            worker = threading.Thread(
                target=self._run_loop,
                args=(camera_id, stop_event),
                name=f"detect-{camera_id}",
                daemon=True,
            )
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

    def status(self, camera_id: str) -> DetectionWorkerStatus:
        detector_status = self.detector.status()
        with self._lock:
            worker = self._workers.get(camera_id)
            stats = self._stats.get(camera_id, DetectionRunStats())
            fps = self._fps.get(camera_id)
            health = self._health.get(camera_id)
        running = bool(worker and worker.is_alive())
        last_error = stats.last_error or detector_status.last_error
        return DetectionWorkerStatus(
            camera_id=camera_id,
            running=running,
            enabled=detector_status.enabled,
            loaded=detector_status.loaded,
            model_name=detector_status.model_name,
            detection_fps=fps.fps if fps else 0.0,
            inference_latency_ms=stats.inference_latency_ms,
            loop_latency_ms=stats.loop_latency_ms,
            lock_wait_avg_ms=detector_status.lock_wait_avg_ms,
            lock_wait_p95_ms=detector_status.lock_wait_p95_ms,
            last_lock_wait_ms=detector_status.last_lock_wait_ms,
            last_error=last_error,
            health=health.snapshot(worker_alive=running) if health else None,
        )

    def _run_loop(self, camera_id: str, stop_event: threading.Event) -> None:
        last_seq = 0
        interval = max(self.settings.detection_interval_ms, 1) / 1000
        next_tick = time.perf_counter()
        logger.info("detection_worker_started camera_id=%s", camera_id)

        while not stop_event.is_set():
            self._mark_health(camera_id, "heartbeat")
            buffer = self.source_manager.get_analysis_buffer(camera_id)
            if buffer is None:
                self._wait_until(next_tick, stop_event)
                next_tick += interval
                continue

            packet = buffer.latest()
            if packet is None or packet.seq == last_seq:
                stop_event.wait(0.03)
                continue
            last_seq = packet.seq
            loop_started = time.perf_counter()
            self._detect_packet(buffer, packet)
            loop_latency_ms = round((time.perf_counter() - loop_started) * 1000, 2)
            with self._lock:
                self._stats[camera_id].loop_latency_ms = loop_latency_ms
            next_tick += interval
            self._wait_until(next_tick, stop_event)

        logger.info("detection_worker_stopped camera_id=%s", camera_id)

    def _detect_packet(self, buffer: FrameBuffer, packet) -> None:
        camera_id = packet.camera_id
        start = time.perf_counter()
        try:
            objects = self.detector.detect(packet.frame)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            self.realtime_store.update_detection(
                DetectionSnapshot(
                    camera_id=camera_id,
                    timestamp=utc_now_iso(),
                    frame_seq=packet.seq,
                    frame_width=packet.width,
                    frame_height=packet.height,
                    monotonic_at=time.monotonic(),
                    frame=packet.frame,
                    objects=objects,
                    detector={
                        "name": "ultralytics_yolo",
                        "mode": "person_detect",
                        "latency_ms": latency_ms,
                    },
                )
            )
            with self._lock:
                self._fps[camera_id].tick()
                self._stats[camera_id].inference_latency_ms = latency_ms
                self._stats[camera_id].lock_wait_ms = self.detector.status().last_lock_wait_ms
                self._stats[camera_id].last_error = None
                self._stats[camera_id].last_detected_at = time.monotonic()
                health = self._health.setdefault(camera_id, WorkerHealthTracker())
                health.mark_success(latency_ms)
        except Exception as exc:
            logger.exception("detection_error camera_id=%s", camera_id)
            with self._lock:
                self._stats[camera_id].last_error = str(exc)
                health = self._health.setdefault(camera_id, WorkerHealthTracker())
                health.mark_error(str(exc))

    def _mark_health(self, camera_id: str, event: str) -> None:
        with self._lock:
            health = self._health.setdefault(camera_id, WorkerHealthTracker())
            if event == "heartbeat":
                health.mark_heartbeat()

    @staticmethod
    def _wait_until(target: float, stop_event: threading.Event) -> None:
        delay = target - time.perf_counter()
        if delay > 0:
            stop_event.wait(delay)
