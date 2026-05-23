from __future__ import annotations

from app.camera.source_manager import CameraSourceManager
from app.camera.source_models import CameraSourceConfig
from app.core.config import Settings
from app.services.detection_service import DetectionService
from app.services.identity_binding_worker_service import IdentityBindingWorkerService
from app.services.identity_binding_service import IdentityBindingService
from app.services.pose_worker_service import PoseWorkerService
from app.services.result_publisher_service import ResultPublisherService
from app.services.temporal_service import TemporalService
from app.services.tracking_service import TrackingService
from app.services.tracking_worker_service import TrackingWorkerService
from app.detection.realtime_result_store import RealtimeResultStore


class StreamService:
    def __init__(
        self,
        settings: Settings,
        source_manager: CameraSourceManager,
        detection_service: DetectionService,
        realtime_store: RealtimeResultStore,
        tracking_service: TrackingService,
        identity_binding_service: IdentityBindingService,
        temporal_service: TemporalService,
        tracking_worker_service: TrackingWorkerService,
        identity_binding_worker_service: IdentityBindingWorkerService,
        pose_worker_service: PoseWorkerService,
        result_publisher_service: ResultPublisherService,
    ) -> None:
        self.settings = settings
        self.source_manager = source_manager
        self.detection_service = detection_service
        self.realtime_store = realtime_store
        self.tracking_service = tracking_service
        self.identity_binding_service = identity_binding_service
        self.temporal_service = temporal_service
        self.tracking_worker_service = tracking_worker_service
        self.identity_binding_worker_service = identity_binding_worker_service
        self.pose_worker_service = pose_worker_service
        self.result_publisher_service = result_publisher_service

    def start(self, camera_id: str, source_url: str | None) -> tuple[bool, str]:
        resolved_url = self._resolve_source_url(source_url)
        self._reset_camera_state(camera_id)
        runtime, created = self.source_manager.start_source(
            CameraSourceConfig(camera_id=camera_id, source_url=resolved_url)
        )
        self.detection_service.start_for_camera(runtime.config.camera_id)
        self.tracking_worker_service.start_for_camera(runtime.config.camera_id)
        self.identity_binding_worker_service.start_for_camera(runtime.config.camera_id)
        self.pose_worker_service.start_for_camera(runtime.config.camera_id)
        self.result_publisher_service.start_for_camera(runtime.config.camera_id)
        if created:
            return True, "stream started"
        return False, "stream already running"

    def stop(self, camera_id: str) -> bool:
        self.result_publisher_service.stop_for_camera(camera_id)
        self.pose_worker_service.stop_for_camera(camera_id)
        self.identity_binding_worker_service.stop_for_camera(camera_id)
        self.tracking_worker_service.stop_for_camera(camera_id)
        self.detection_service.stop_for_camera(camera_id)
        return self.source_manager.stop_source(camera_id)

    def _reset_camera_state(self, camera_id: str) -> None:
        self.tracking_service.reset(camera_id)
        self.identity_binding_service.reset_camera(camera_id)
        self.temporal_service.reset_camera(camera_id)
        self.realtime_store.clear_camera(camera_id)

    def _resolve_source_url(self, source_url: str | None) -> str:
        if source_url:
            return source_url
        if self.settings.default_rtsp_url:
            return self.settings.default_rtsp_url
        if self.settings.mock_camera_enabled:
            return "mock://colorbars"
        raise ValueError("rtsp_url is required when mock camera is disabled")
