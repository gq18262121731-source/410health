from __future__ import annotations

from app.camera.source_manager import CameraSourceManager
from app.camera.source_models import mask_source_url
from app.detection.realtime_result_store import RealtimeResultStore
from app.schemas.status import (
    BehaviorStatus,
    CameraStatus,
    DetectionStatus,
    DiagnosticsStatus,
    IdentityStatus,
    PipelineStatus,
    PoseStatus,
    StreamingStatus,
    StreamRuntimeStatus,
    TemporalStatus,
    TrackingStatus,
    VisionStatus,
    WatchdogStatus,
    WorkerHealthStatus,
    WorkerStatusGroup,
)
from app.services.behavior_service import BehaviorService
from app.services.detection_service import DetectionService
from app.services.identity_binding_service import IdentityBindingService
from app.services.identity_binding_worker_service import IdentityBindingWorkerService
from app.services.identity_service import IdentityService
from app.services.pose_service import PoseService
from app.services.pose_worker_service import PoseWorkerService
from app.services.result_publisher_service import ResultPublisherService
from app.services.temporal_service import TemporalService
from app.services.tracking_service import TrackingService
from app.services.tracking_worker_service import TrackingWorkerService
from app.services.watchdog_service import WatchdogService
from app.streaming.peer_manager import PeerManager
from app.streaming.result_channel_manager import ResultChannelManager


class StatusService:
    def __init__(
        self,
        source_manager: CameraSourceManager,
        detection_service: DetectionService,
        peer_manager: PeerManager,
        result_channels: ResultChannelManager,
        realtime_store: RealtimeResultStore,
        tracking_service: TrackingService | None = None,
        tracking_worker_service: TrackingWorkerService | None = None,
        identity_service: IdentityService | None = None,
        identity_binding_service: IdentityBindingService | None = None,
        identity_binding_worker_service: IdentityBindingWorkerService | None = None,
        pose_service: PoseService | None = None,
        pose_worker_service: PoseWorkerService | None = None,
        behavior_service: BehaviorService | None = None,
        temporal_service: TemporalService | None = None,
        result_publisher_service: ResultPublisherService | None = None,
        watchdog_service: WatchdogService | None = None,
    ) -> None:
        self.source_manager = source_manager
        self.detection_service = detection_service
        self.peer_manager = peer_manager
        self.result_channels = result_channels
        self.realtime_store = realtime_store
        self.tracking_service = tracking_service
        self.tracking_worker_service = tracking_worker_service
        self.identity_service = identity_service
        self.identity_binding_service = identity_binding_service
        self.identity_binding_worker_service = identity_binding_worker_service
        self.pose_service = pose_service
        self.pose_worker_service = pose_worker_service
        self.behavior_service = behavior_service
        self.temporal_service = temporal_service
        self.result_publisher_service = result_publisher_service
        self.watchdog_service = watchdog_service

    def status(self, camera_id: str | None = None) -> VisionStatus:
        runtimes = self.source_manager.list_runtimes()
        if camera_id:
            runtimes = [runtime for runtime in runtimes if runtime.config.camera_id == camera_id]

        cameras: list[CameraStatus] = []
        detections: list[DetectionStatus] = []
        main_stream = StreamRuntimeStatus()
        analysis_stream = StreamRuntimeStatus()
        main_worker_status = None
        analysis_worker_status = None
        display_source = "single"
        analysis_source = "single"
        display_source_current = "single"
        display_fallback_active = False
        for runtime in runtimes:
            worker_status = runtime.analysis_worker.status()
            main_worker_status = runtime.main_worker.status() if runtime.main_worker else worker_status
            analysis_worker_status = (
                runtime.analysis_worker.status() if runtime.analysis_worker else worker_status
            )
            main_stream = self._stream_runtime_status(
                enabled=True,
                source_url=runtime.main_config.source_url if runtime.main_config else runtime.config.source_url,
                worker_status=main_worker_status,
            )
            analysis_stream = self._stream_runtime_status(
                enabled=True,
                source_url=(
                    runtime.analysis_config.source_url
                    if runtime.analysis_config
                    else runtime.config.source_url
                ),
                worker_status=analysis_worker_status,
            )
            display_source = "main" if runtime.dual_stream_enabled else "single"
            analysis_source = "analysis" if runtime.dual_stream_enabled else "single"
            display_source_current, display_fallback_active = self.source_manager.display_state(
                runtime.config.camera_id
            )
            cameras.append(
                CameraStatus(
                    camera_id=runtime.config.camera_id,
                    running=worker_status.running,
                    connected=worker_status.connected,
                    source_url=runtime.config.source_url,
                    source_url_masked=mask_source_url(runtime.config.source_url),
                    frame_seq=worker_status.frame_seq,
                    frame_width=worker_status.frame_width,
                    frame_height=worker_status.frame_height,
                    frame_age_ms=worker_status.frame_age_ms,
                    last_frame_at=worker_status.last_frame_at,
                    stream_state=worker_status.stream_state,
                    capture_fps=worker_status.capture_fps,
                    reconnect_count=worker_status.reconnect_count,
                    read_latency_ms=worker_status.read_latency_ms,
                    read_latency_avg_ms=worker_status.read_latency_avg_ms,
                    read_latency_max_ms=worker_status.read_latency_max_ms,
                    read_timeout_count=worker_status.read_timeout_count,
                    stale_count=worker_status.stale_count,
                    last_read_started_at=worker_status.last_read_started_at,
                    last_read_completed_at=worker_status.last_read_completed_at,
                    consecutive_slow_reads=worker_status.consecutive_slow_reads,
                    reconnect_reason=worker_status.reconnect_reason,
                    capture_backend=worker_status.capture_backend,
                    capture_process_alive=worker_status.capture_process_alive,
                    capture_process_pid=worker_status.capture_process_pid,
                    capture_process_restart_count=worker_status.capture_process_restart_count,
                    capture_process_last_frame_age_ms=worker_status.capture_process_last_frame_age_ms,
                    capture_process_last_error=worker_status.capture_process_last_error,
                    capture_process_last_exit_code=worker_status.capture_process_last_exit_code,
                    capture_process_last_log=worker_status.capture_process_last_log,
                    capture_process_last_failure_reason=worker_status.capture_process_last_failure_reason,
                    capture_process_open_started_at=worker_status.capture_process_open_started_at,
                    capture_process_opened_at=worker_status.capture_process_opened_at,
                    capture_process_first_frame_at=worker_status.capture_process_first_frame_at,
                    capture_process_source_fps=worker_status.capture_process_source_fps,
                    capture_ipc_decode_errors=worker_status.capture_ipc_decode_errors,
                    capture_ipc_dropped_frames=worker_status.capture_ipc_dropped_frames,
                    capture_output_width=worker_status.capture_output_width,
                    capture_output_height=worker_status.capture_output_height,
                    last_error=worker_status.last_error,
                )
            )
            detection_status = self.detection_service.status(runtime.config.camera_id)
            detections.append(
                DetectionStatus(
                    camera_id=detection_status.camera_id,
                    running=detection_status.running,
                    enabled=detection_status.enabled,
                    loaded=detection_status.loaded,
                    model_name=detection_status.model_name,
                    detection_fps=detection_status.detection_fps,
                    inference_latency_ms=detection_status.inference_latency_ms,
                    loop_latency_ms=detection_status.loop_latency_ms,
                    lock_wait_avg_ms=detection_status.lock_wait_avg_ms,
                    lock_wait_p95_ms=detection_status.lock_wait_p95_ms,
                    last_lock_wait_ms=detection_status.last_lock_wait_ms,
                    last_error=detection_status.last_error,
                )
            )

        tracking_status = TrackingStatus()
        if self.tracking_service is not None:
            tracking_camera_id = camera_id
            if tracking_camera_id is None and runtimes:
                tracking_camera_id = runtimes[0].config.camera_id
            if tracking_camera_id:
                raw_tracking_status = self.tracking_service.status(tracking_camera_id)
                tracking_status = TrackingStatus(**raw_tracking_status.model_dump())

        identity_status = IdentityStatus()
        if self.identity_service is not None:
            raw_identity_status = self.identity_service.status()
            identity_status = IdentityStatus(
                identity_enabled=raw_identity_status.identity_enabled,
                identity_binding_enabled=False,
                recognizer_loaded=raw_identity_status.recognizer_loaded,
                recognizer_name=raw_identity_status.recognizer_name,
                model_name=raw_identity_status.model_name,
                registered_count=raw_identity_status.registered_count,
                last_error=raw_identity_status.last_error,
            )
        if self.identity_binding_service is not None:
            identity_status.identity_binding_enabled = self.identity_binding_service.settings.enable_identity_binding
            identity_status.identity_service_available = self.identity_binding_service.service_available
            identity_status.recognizer_loaded = self.identity_binding_service.recognizer_loaded or identity_status.recognizer_loaded
            identity_status.registered_count = max(
                identity_status.registered_count,
                self.identity_binding_service.registered_count,
            )
            identity_status.bound_person_id = self.identity_binding_service.bound_person_id
            identity_status.bound_person_name = self.identity_binding_service.bound_person_name
            identity_status.last_match_score = self.identity_binding_service.last_match_score
            identity_status.cache_age_ms = self.identity_binding_service.cache_age_ms
            identity_status.last_match_latency_ms = self.identity_binding_service.last_match_latency_ms
            identity_status.pending_requests = self.identity_binding_service.pending_requests
            identity_status.skipped_due_to_inflight = self.identity_binding_service.skipped_due_to_inflight
            identity_status.health_cache_age_ms = self.identity_binding_service.health_cache_age_ms
            identity_status.last_error = self.identity_binding_service.last_error or identity_status.last_error
            if self.identity_binding_worker_service is not None:
                worker_error = self.identity_binding_worker_service.last_error(
                    camera_id or (runtimes[0].config.camera_id if runtimes else "")
                )
                identity_status.last_error = worker_error or identity_status.last_error

        pose_status = PoseStatus()
        if self.pose_service is not None:
            pose_camera_id = camera_id
            if pose_camera_id is None and runtimes:
                pose_camera_id = runtimes[0].config.camera_id
            raw_pose_status = self.pose_service.status(pose_camera_id)
            pose_status = PoseStatus(**raw_pose_status.model_dump())

        behavior_status = BehaviorStatus()
        if self.behavior_service is not None:
            behavior_camera_id = camera_id
            if behavior_camera_id is None and runtimes:
                behavior_camera_id = runtimes[0].config.camera_id
            raw_behavior_status = self.behavior_service.status(behavior_camera_id)
            behavior_status = BehaviorStatus(**raw_behavior_status.model_dump())

        temporal_status = TemporalStatus()
        if self.temporal_service is not None:
            temporal_camera_id = camera_id
            if temporal_camera_id is None and runtimes:
                temporal_camera_id = runtimes[0].config.camera_id
            raw_temporal_status = self.temporal_service.status(temporal_camera_id)
            temporal_status = TemporalStatus(**raw_temporal_status.model_dump())

        pipeline_status = PipelineStatus()
        pipeline_camera_id = camera_id
        if pipeline_camera_id is None and runtimes:
            pipeline_camera_id = runtimes[0].config.camera_id
        if pipeline_camera_id:
            snapshot = self.realtime_store.snapshot(pipeline_camera_id)
            publisher_error = (
                self.result_publisher_service.last_error(pipeline_camera_id)
                if self.result_publisher_service is not None
                else None
            )
            tracking_worker_error = (
                self.tracking_worker_service.last_error(pipeline_camera_id)
                if self.tracking_worker_service is not None
                else None
            )
            pipeline_status = PipelineStatus(
                detection_worker_fps=detections[0].detection_fps if detections else 0.0,
                tracking_worker_fps=(
                    self.tracking_worker_service.status_fps(pipeline_camera_id)
                    if self.tracking_worker_service is not None
                    else 0.0
                ),
                result_publish_fps=(
                    self.result_publisher_service.status_fps(pipeline_camera_id)
                    if self.result_publisher_service is not None
                    else 0.0
                ),
                latest_detection_age_ms=self.realtime_store.age_ms(
                    snapshot.latest_detection.monotonic_at if snapshot.latest_detection else None
                ),
                latest_tracking_age_ms=self.realtime_store.age_ms(
                    snapshot.latest_tracking.monotonic_at if snapshot.latest_tracking else None
                ),
                latest_pose_age_ms=self.realtime_store.age_ms(
                    snapshot.latest_pose.monotonic_at if snapshot.latest_pose else None
                ),
                detection_to_publish_lag_ms=(
                    self.result_publisher_service.detection_to_publish_lag_ms(pipeline_camera_id)
                    if self.result_publisher_service is not None
                    else None
                ),
                capture_queue_size=0,
                detection_queue_size=0,
                tracking_queue_size=0,
                pose_queue_size=0,
                publish_queue_size=0,
                dropped_frames=self._dropped_frames(main_worker_status, analysis_worker_status),
                last_error=publisher_error or tracking_worker_error,
            )

        streaming_status = StreamingStatus(
            webrtc_clients=self.peer_manager.client_count,
            ws_clients=self.result_channels.subscriber_count,
        )
        workers_status = self._workers_status(
            camera_id=pipeline_camera_id,
            main_worker_status=main_worker_status,
            analysis_worker_status=analysis_worker_status,
        )
        diagnostics_status = self._diagnostics_status(
            main_stream=main_stream,
            analysis_stream=analysis_stream,
            detections=detections,
            pose_status=pose_status,
            pipeline_status=pipeline_status,
            streaming_status=streaming_status,
        )
        service_state = self._service_state(diagnostics_status)
        watchdog_status = self._watchdog_status()
        if watchdog_status.watchdog_state == "degraded":
            service_state = "degraded"

        return VisionStatus(
            service_state=service_state,
            cameras=cameras,
            detection=detections,
            streaming=streaming_status,
            workers=workers_status,
            diagnostics=diagnostics_status,
            watchdog=watchdog_status,
            main_stream=main_stream,
            analysis_stream=analysis_stream,
            display_source=display_source,
            analysis_source=analysis_source,
            display_source_current=display_source_current,
            display_fallback_active=display_fallback_active,
            tracking=tracking_status,
            identity=identity_status,
            pose=pose_status,
            behavior=behavior_status,
            temporal=temporal_status,
            pipeline=pipeline_status,
        )

    def _watchdog_status(self) -> WatchdogStatus:
        if self.watchdog_service is None:
            return WatchdogStatus()
        raw = self.watchdog_service.status()
        return WatchdogStatus(
            watchdog_enabled=raw.watchdog_enabled,
            watchdog_state=raw.watchdog_state,
            watchdog_last_action=raw.watchdog_last_action,
            watchdog_restart_count=raw.watchdog_restart_count,
            watchdog_suppressed=raw.watchdog_suppressed,
            degraded_reason=raw.degraded_reason,
            last_checked_at=raw.last_checked_at,
            last_action_at=raw.last_action_at,
            suppressed_workers=raw.suppressed_workers,
        )

    @staticmethod
    def _stream_runtime_status(
        enabled: bool,
        source_url: str | None,
        worker_status,
    ) -> StreamRuntimeStatus:
        return StreamRuntimeStatus(
            enabled=enabled,
            source_url=source_url,
            source_url_masked=mask_source_url(source_url),
            stream_state=worker_status.stream_state,
            connected=worker_status.connected,
            frame_width=worker_status.frame_width,
            frame_height=worker_status.frame_height,
            frame_age_ms=worker_status.frame_age_ms,
            capture_fps=worker_status.capture_fps,
            capture_backend=worker_status.capture_backend,
            restart_count=worker_status.reconnect_count,
            last_restart_at=worker_status.last_restart_at,
            last_restart_reason=worker_status.last_restart_reason,
            last_error=worker_status.last_error,
        )

    def _workers_status(
        self,
        *,
        camera_id: str | None,
        main_worker_status,
        analysis_worker_status,
    ) -> WorkerStatusGroup:
        capture_main = self._capture_worker_health(main_worker_status)
        capture_analysis = self._capture_worker_health(analysis_worker_status)
        if camera_id is None:
            return WorkerStatusGroup(
                capture_main=capture_main,
                capture_analysis=capture_analysis,
            )

        detection_health = None
        detection_status = self.detection_service.status(camera_id)
        if detection_status.health is not None:
            detection_health = self._health_status(detection_status.health)

        tracking_health = (
            self._health_status(self.tracking_worker_service.health(camera_id))
            if self.tracking_worker_service is not None
            else WorkerHealthStatus()
        )
        pose_health = (
            self._health_status(self.pose_worker_service.health(camera_id))
            if self.pose_worker_service is not None
            else WorkerHealthStatus()
        )
        publisher_health = (
            self._health_status(self.result_publisher_service.health(camera_id))
            if self.result_publisher_service is not None
            else WorkerHealthStatus()
        )

        return WorkerStatusGroup(
            capture_main=capture_main,
            capture_analysis=capture_analysis,
            detection=detection_health or WorkerHealthStatus(),
            tracking=tracking_health,
            pose=pose_health,
            result_publisher=publisher_health,
        )

    @staticmethod
    def _health_status(snapshot) -> WorkerHealthStatus:
        return WorkerHealthStatus(
            worker_alive=snapshot.worker_alive,
            heartbeat_at=snapshot.heartbeat_at,
            last_success_at=snapshot.last_success_at,
            error_count=snapshot.error_count,
            restart_count=snapshot.restart_count,
            last_error=snapshot.last_error,
            avg_latency_ms=snapshot.avg_latency_ms,
            last_latency_ms=snapshot.last_latency_ms,
        )

    @staticmethod
    def _dropped_frames(*worker_statuses) -> int:
        total = 0
        for worker_status in worker_statuses:
            if worker_status is None:
                continue
            total += int(worker_status.capture_ipc_dropped_frames or 0)
        return total

    @staticmethod
    def _capture_worker_health(worker_status) -> WorkerHealthStatus:
        if worker_status is None:
            return WorkerHealthStatus()
        restart_count = worker_status.capture_process_restart_count or worker_status.reconnect_count
        return WorkerHealthStatus(
            worker_alive=bool(worker_status.running),
            heartbeat_at=worker_status.last_read_completed_at or worker_status.last_frame_at,
            last_success_at=worker_status.last_frame_at,
            error_count=worker_status.read_timeout_count,
            restart_count=restart_count,
            last_error=worker_status.last_error or worker_status.capture_process_last_error,
            avg_latency_ms=worker_status.read_latency_avg_ms,
            last_latency_ms=worker_status.read_latency_ms,
        )

    def _diagnostics_status(
        self,
        *,
        main_stream: StreamRuntimeStatus,
        analysis_stream: StreamRuntimeStatus,
        detections: list[DetectionStatus],
        pose_status: PoseStatus,
        pipeline_status: PipelineStatus,
        streaming_status: StreamingStatus,
    ) -> DiagnosticsStatus:
        camera_lost = self._is_camera_lost(main_stream, analysis_stream)
        capture_stale = self._is_capture_stale(main_stream, analysis_stream)
        detection = detections[0] if detections else None
        inference_slow = bool(
            detection
            and detection.enabled
            and (
                (detection.inference_latency_ms or 0) > 1000
                or pipeline_status.detection_worker_fps < 1.0
            )
        )
        pose_degraded = bool(
            pose_status.pose_enabled
            and (
                pose_status.circuit_open
                or pose_status.slow_inference_count >= 2
                or pose_status.skipped_due_to_busy >= 50
            )
        )
        publisher_slow = bool(
            pipeline_status.result_publish_fps > 0
            and pipeline_status.result_publish_fps < 6
        )
        frontend_disconnected = (
            streaming_status.webrtc_clients == 0
            and streaming_status.ws_clients == 0
        )
        return DiagnosticsStatus(
            camera_lost=camera_lost,
            capture_stale=capture_stale,
            inference_slow=inference_slow,
            pose_degraded=pose_degraded,
            publisher_slow=publisher_slow,
            frontend_disconnected=frontend_disconnected,
        )

    @staticmethod
    def _is_camera_lost(main_stream: StreamRuntimeStatus, analysis_stream: StreamRuntimeStatus) -> bool:
        enabled = [stream for stream in (main_stream, analysis_stream) if stream.enabled]
        if not enabled:
            return False
        return all(stream.stream_state in {"disconnected", "reconnecting", "connecting"} for stream in enabled)

    @staticmethod
    def _is_capture_stale(main_stream: StreamRuntimeStatus, analysis_stream: StreamRuntimeStatus) -> bool:
        for stream in (main_stream, analysis_stream):
            if not stream.enabled:
                continue
            if stream.stream_state == "stale":
                return True
            if stream.frame_age_ms is not None and stream.frame_age_ms > 3000:
                return True
        return False

    @staticmethod
    def _service_state(diagnostics: DiagnosticsStatus) -> str:
        if diagnostics.camera_lost:
            return "camera_lost"
        if diagnostics.capture_stale:
            return "capture_stale"
        if diagnostics.inference_slow:
            return "inference_slow"
        if diagnostics.publisher_slow:
            return "publisher_slow"
        if diagnostics.pose_degraded:
            return "degraded"
        if diagnostics.frontend_disconnected:
            return "frontend_disconnected"
        return "normal"
