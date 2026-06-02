from __future__ import annotations

import threading
import time

from app.core.config import Settings
from app.core.logger import get_logger
from app.camera.source_manager import CameraSourceManager
from app.detection.realtime_result_store import ObjectSnapshot, RealtimeResultStore
from app.detection.result_store import ResultStore
from app.monitoring.metrics import FPSMeter
from app.monitoring.worker_health import WorkerHealthSnapshot, WorkerHealthTracker
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
        result_store: ResultStore,
        result_channels: ResultChannelManager,
        temporal_service: TemporalService | None = None,
        source_manager: CameraSourceManager | None = None,
    ) -> None:
        self.settings = settings
        self.realtime_store = realtime_store
        self.result_store = result_store
        self.result_channels = result_channels
        self.temporal_service = temporal_service
        self.source_manager = source_manager
        self._workers: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._fps: dict[str, FPSMeter] = {}
        self._last_error: dict[str, str | None] = {}
        self._last_detection_to_publish_lag_ms: dict[str, float | None] = {}
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
                name=f"result-publisher-{camera_id}",
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

    def health(self, camera_id: str) -> WorkerHealthSnapshot:
        with self._lock:
            worker = self._workers.get(camera_id)
            health = self._health.setdefault(camera_id, WorkerHealthTracker())
        return health.snapshot(worker_alive=bool(worker and worker.is_alive()))

    def _run_loop(self, camera_id: str, stop_event: threading.Event) -> None:
        interval = 1 / max(self.settings.result_publish_fps, 1)
        logger.info("result_publisher_started camera_id=%s", camera_id)
        while not stop_event.is_set():
            tick_started = time.perf_counter()
            try:
                result = self._build_result(camera_id)
                if result is not None:
                    self.realtime_store.update_published(result)
                    self.result_store.update(result)
                    self.result_channels.publish(result)
                    latency_ms = (time.perf_counter() - tick_started) * 1000
                    with self._lock:
                        self._fps.setdefault(camera_id, FPSMeter()).tick()
                        self._last_error[camera_id] = None
                        self._health.setdefault(camera_id, WorkerHealthTracker()).mark_success(latency_ms)
                else:
                    with self._lock:
                        self._last_error[camera_id] = None
                        self._health.setdefault(camera_id, WorkerHealthTracker()).mark_heartbeat()
            except Exception as exc:
                logger.exception("result_publisher_error camera_id=%s", camera_id)
                with self._lock:
                    self._last_error[camera_id] = str(exc)
                    self._health.setdefault(camera_id, WorkerHealthTracker()).mark_error(str(exc))
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

        frame_metadata = self._frame_metadata(camera_id, base.frame_width, base.frame_height)

        return VisionResult(
            camera_id=camera_id,
            timestamp=utc_now_iso(),
            frame_seq=base.frame_seq,
            frame_width=base.frame_width,
            frame_height=base.frame_height,
            analysis_frame_width=frame_metadata["analysis_frame_width"],
            analysis_frame_height=frame_metadata["analysis_frame_height"],
            display_frame_width=frame_metadata["display_frame_width"],
            display_frame_height=frame_metadata["display_frame_height"],
            display_source=frame_metadata["display_source"],
            analysis_source=frame_metadata["analysis_source"],
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

    def _frame_metadata(self, camera_id: str, fallback_width: int, fallback_height: int) -> dict:
        analysis_width = fallback_width
        analysis_height = fallback_height
        display_width = fallback_width
        display_height = fallback_height
        display_source = "single"
        analysis_source = "single"

        runtime = self.source_manager.get_runtime(camera_id) if self.source_manager else None
        if runtime is None:
            return {
                "analysis_frame_width": analysis_width,
                "analysis_frame_height": analysis_height,
                "display_frame_width": display_width,
                "display_frame_height": display_height,
                "display_source": display_source,
                "analysis_source": analysis_source,
            }

        if runtime.dual_stream_enabled:
            if self.source_manager is not None:
                display_source, _ = self.source_manager.display_state(camera_id)
            else:
                display_source = runtime.display_source_current or "main"
            analysis_source = "analysis"

        analysis_status = runtime.analysis_worker.status() if runtime.analysis_worker else None
        if display_source == "analysis":
            display_status = analysis_status
        else:
            display_status = runtime.main_worker.status() if runtime.main_worker else analysis_status

        if analysis_status and analysis_status.frame_width and analysis_status.frame_height:
            analysis_width = analysis_status.frame_width
            analysis_height = analysis_status.frame_height
        if display_status and display_status.frame_width and display_status.frame_height:
            display_width = display_status.frame_width
            display_height = display_status.frame_height

        return {
            "analysis_frame_width": analysis_width,
            "analysis_frame_height": analysis_height,
            "display_frame_width": display_width,
            "display_frame_height": display_height,
            "display_source": display_source,
            "analysis_source": analysis_source,
        }
