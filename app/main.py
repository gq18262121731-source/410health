from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import identity_api, rest_api, status_api, webrtc_api, ws_api
from app.camera.source_manager import CameraSourceManager
from app.core.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.core.runtime import Runtime
from app.detection.realtime_result_store import RealtimeResultStore
from app.detection.result_store import ResultStore
from app.services.behavior_service import BehaviorService
from app.services.detection_service import DetectionService
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
from app.integration.identity_client import IdentityClient
from app.streaming.peer_manager import PeerManager
from app.streaming.result_channel_manager import ResultChannelManager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    source_manager = CameraSourceManager(settings)
    realtime_store = RealtimeResultStore()
    result_store = ResultStore()
    result_channels = ResultChannelManager()
    result_channels.bind_loop(asyncio.get_running_loop())
    tracking_service = TrackingService(settings=settings)
    identity_service = IdentityService(settings=settings)
    identity_client = IdentityClient(settings=settings)
    identity_binding_service = IdentityBindingService(settings=settings, client=identity_client)
    identity_binding_worker_service = IdentityBindingWorkerService(
        settings=settings,
        source_manager=source_manager,
        realtime_store=realtime_store,
        identity_binding_service=identity_binding_service,
    )
    pose_service = PoseService(settings=settings)
    behavior_service = BehaviorService(settings=settings)
    temporal_service = TemporalService(settings=settings)
    detection_service = DetectionService(
        settings=settings,
        source_manager=source_manager,
        realtime_store=realtime_store,
    )
    tracking_worker_service = TrackingWorkerService(
        settings=settings,
        realtime_store=realtime_store,
        tracking_service=tracking_service,
        identity_binding_service=identity_binding_service,
    )
    pose_worker_service = PoseWorkerService(
        settings=settings,
        source_manager=source_manager,
        realtime_store=realtime_store,
        pose_service=pose_service,
        behavior_service=behavior_service,
    )
    result_publisher_service = ResultPublisherService(
        settings=settings,
        realtime_store=realtime_store,
        result_channels=result_channels,
        temporal_service=temporal_service,
    )
    stream_service = StreamService(
        settings=settings,
        source_manager=source_manager,
        detection_service=detection_service,
        realtime_store=realtime_store,
        tracking_service=tracking_service,
        identity_binding_service=identity_binding_service,
        temporal_service=temporal_service,
        tracking_worker_service=tracking_worker_service,
        identity_binding_worker_service=identity_binding_worker_service,
        pose_worker_service=pose_worker_service,
        result_publisher_service=result_publisher_service,
    )
    peer_manager = PeerManager(settings=settings, source_manager=source_manager)
    status_service = StatusService(
        source_manager=source_manager,
        detection_service=detection_service,
        peer_manager=peer_manager,
        result_channels=result_channels,
        realtime_store=realtime_store,
        tracking_service=tracking_service,
        tracking_worker_service=tracking_worker_service,
        identity_service=identity_service,
        identity_binding_service=identity_binding_service,
        identity_binding_worker_service=identity_binding_worker_service,
        pose_service=pose_service,
        behavior_service=behavior_service,
        temporal_service=temporal_service,
        result_publisher_service=result_publisher_service,
    )
    runtime = Runtime(
        settings=settings,
        source_manager=source_manager,
        realtime_store=realtime_store,
        result_store=result_store,
        result_channels=result_channels,
        tracking_service=tracking_service,
        detection_service=detection_service,
        identity_service=identity_service,
        identity_binding_service=identity_binding_service,
        identity_binding_worker_service=identity_binding_worker_service,
        pose_service=pose_service,
        behavior_service=behavior_service,
        temporal_service=temporal_service,
        tracking_worker_service=tracking_worker_service,
        pose_worker_service=pose_worker_service,
        result_publisher_service=result_publisher_service,
        stream_service=stream_service,
        peer_manager=peer_manager,
        status_service=status_service,
    )
    app.state.runtime = runtime

    if settings.default_rtsp_url or settings.mock_camera_enabled:
        try:
            runtime.stream_service.start(settings.default_camera_id, settings.default_rtsp_url)
            logger.info("default_stream_started camera_id=%s", settings.default_camera_id)
        except Exception:
            logger.exception("default_stream_start_failed")

    try:
        yield
    finally:
        await runtime.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="Vision Service", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(status_api.router)
    app.include_router(rest_api.router)
    app.include_router(webrtc_api.router)
    app.include_router(ws_api.router)
    app.include_router(identity_api.router)

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend_demo"
    if frontend_dir.exists():
        app.mount("/demo", StaticFiles(directory=frontend_dir, html=True), name="demo")
    return app


app = create_app()
