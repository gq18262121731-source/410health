from __future__ import annotations

from dataclasses import dataclass

from app.camera.source_manager import CameraSourceManager
from app.core.config import Settings
from app.detection.realtime_result_store import RealtimeResultStore
from app.detection.result_store import ResultStore
from app.services.detection_service import DetectionService
from app.services.behavior_service import BehaviorService
from app.services.identity_binding_service import IdentityBindingService
from app.services.identity_binding_worker_service import IdentityBindingWorkerService
from app.services.identity_service import IdentityService
from app.services.pose_service import PoseService
from app.services.pose_worker_service import PoseWorkerService
from app.services.result_publisher_service import ResultPublisherService
from app.services.status_service import StatusService
from app.services.stream_service import StreamService
from app.services.temporal_service import TemporalService
from app.services.tracking_service import TrackingService
from app.services.tracking_worker_service import TrackingWorkerService
from app.services.video_bridge_publisher_service import VideoBridgePublisherService
from app.services.watchdog_service import WatchdogService
from app.streaming.peer_manager import PeerManager
from app.streaming.result_channel_manager import ResultChannelManager


@dataclass
class Runtime:
    settings: Settings
    source_manager: CameraSourceManager
    realtime_store: RealtimeResultStore
    result_store: ResultStore
    result_channels: ResultChannelManager
    tracking_service: TrackingService
    identity_service: IdentityService
    identity_binding_service: IdentityBindingService
    identity_binding_worker_service: IdentityBindingWorkerService
    pose_service: PoseService
    behavior_service: BehaviorService
    temporal_service: TemporalService
    detection_service: DetectionService
    tracking_worker_service: TrackingWorkerService
    pose_worker_service: PoseWorkerService
    result_publisher_service: ResultPublisherService
    stream_service: StreamService
    peer_manager: PeerManager
    status_service: StatusService
    watchdog_service: WatchdogService | None = None
    video_bridge_publisher_service: VideoBridgePublisherService | None = None

    async def shutdown(self) -> None:
        if self.watchdog_service is not None:
            self.watchdog_service.stop()
        if self.video_bridge_publisher_service is not None:
            self.video_bridge_publisher_service.stop_all()
        self.result_publisher_service.stop_all()
        self.pose_worker_service.stop_all()
        self.identity_binding_worker_service.stop_all()
        self.tracking_worker_service.stop_all()
        self.detection_service.stop_all()
        self.source_manager.stop_all()
        await self.peer_manager.close_all()
