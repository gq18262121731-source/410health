from __future__ import annotations

from pydantic import BaseModel, Field


class CameraStatus(BaseModel):
    camera_id: str
    running: bool
    connected: bool
    source_url: str | None = None
    source_url_masked: str | None = None
    frame_seq: int = 0
    frame_width: int | None = None
    frame_height: int | None = None
    frame_age_ms: float | None = None
    last_frame_at: str | None = None
    stream_state: str = "disconnected"
    capture_fps: float = 0.0
    reconnect_count: int = 0
    read_latency_ms: float | None = None
    read_latency_avg_ms: float | None = None
    read_latency_max_ms: float | None = None
    read_timeout_count: int = 0
    stale_count: int = 0
    last_read_started_at: str | None = None
    last_read_completed_at: str | None = None
    consecutive_slow_reads: int = 0
    reconnect_reason: str | None = None
    capture_backend: str = "opencv"
    capture_process_alive: bool = False
    capture_process_pid: int | None = None
    capture_process_restart_count: int = 0
    capture_process_last_frame_age_ms: float | None = None
    capture_process_last_error: str | None = None
    capture_process_last_exit_code: int | None = None
    capture_process_last_log: str | None = None
    capture_process_last_failure_reason: str | None = None
    capture_process_open_started_at: str | None = None
    capture_process_opened_at: str | None = None
    capture_process_first_frame_at: str | None = None
    capture_process_source_fps: float | None = None
    capture_ipc_decode_errors: int = 0
    capture_ipc_dropped_frames: int = 0
    capture_output_width: int | None = None
    capture_output_height: int | None = None
    last_error: str | None = None


class StreamRuntimeStatus(BaseModel):
    enabled: bool = False
    source_url: str | None = None
    source_url_masked: str | None = None
    stream_state: str = "disconnected"
    connected: bool = False
    frame_width: int | None = None
    frame_height: int | None = None
    frame_age_ms: float | None = None
    capture_fps: float = 0.0
    capture_backend: str = "opencv"
    restart_count: int = 0
    last_restart_at: str | None = None
    last_restart_reason: str | None = None
    last_error: str | None = None


class DetectionStatus(BaseModel):
    camera_id: str
    running: bool
    enabled: bool
    loaded: bool
    model_name: str | None = None
    detection_fps: float = 0.0
    inference_latency_ms: float | None = None
    loop_latency_ms: float | None = None
    lock_wait_avg_ms: float | None = None
    lock_wait_p95_ms: float | None = None
    last_lock_wait_ms: float | None = None
    last_error: str | None = None


class StreamingStatus(BaseModel):
    webrtc_clients: int = 0
    ws_clients: int = 0


class WorkerHealthStatus(BaseModel):
    worker_alive: bool = False
    heartbeat_at: str | None = None
    last_success_at: str | None = None
    error_count: int = 0
    restart_count: int = 0
    last_error: str | None = None
    avg_latency_ms: float | None = None
    last_latency_ms: float | None = None


class WorkerStatusGroup(BaseModel):
    capture_main: WorkerHealthStatus = Field(default_factory=WorkerHealthStatus)
    capture_analysis: WorkerHealthStatus = Field(default_factory=WorkerHealthStatus)
    detection: WorkerHealthStatus = Field(default_factory=WorkerHealthStatus)
    tracking: WorkerHealthStatus = Field(default_factory=WorkerHealthStatus)
    pose: WorkerHealthStatus = Field(default_factory=WorkerHealthStatus)
    result_publisher: WorkerHealthStatus = Field(default_factory=WorkerHealthStatus)


class DiagnosticsStatus(BaseModel):
    camera_lost: bool = False
    capture_stale: bool = False
    inference_slow: bool = False
    pose_degraded: bool = False
    publisher_slow: bool = False
    frontend_disconnected: bool = False


class WatchdogStatus(BaseModel):
    watchdog_enabled: bool = False
    watchdog_state: str = "disabled"
    watchdog_last_action: str | None = None
    watchdog_restart_count: int = 0
    watchdog_suppressed: bool = False
    degraded_reason: str | None = None
    last_checked_at: str | None = None
    last_action_at: str | None = None
    suppressed_workers: list[str] = Field(default_factory=list)


class TrackingStatus(BaseModel):
    tracker_running: bool = False
    tracking_state: str = "idle"
    tracked_target_id: int | None = None
    active_target_exists: bool = False
    tracked_objects_count: int = 0
    tracking_fps: float = 0.0
    last_error: str | None = None


class IdentityStatus(BaseModel):
    identity_enabled: bool = False
    identity_binding_enabled: bool = False
    identity_service_available: bool = False
    recognizer_loaded: bool = False
    recognizer_name: str | None = None
    model_name: str | None = None
    registered_count: int = 0
    bound_person_id: str | None = None
    bound_person_name: str | None = None
    last_match_score: float | None = None
    cache_age_ms: float | None = None
    last_match_latency_ms: float | None = None
    pending_requests: int = 0
    skipped_due_to_inflight: int = 0
    health_cache_age_ms: float | None = None
    last_error: str | None = None


class PoseStatus(BaseModel):
    pose_enabled: bool = False
    pose_provider: str = "mock"
    pose_fps: float = 0.0
    pose_attempts: int = 0
    pose_success: int = 0
    detection_objects_count: int = 0
    tracking_objects_count: int = 0
    target_objects_count: int = 0
    last_identity_state: str | None = None
    pose_target_source: str = "none"
    fallback_used_count: int = 0
    last_fallback_reason: str | None = None
    pose_objects_count: int = 0
    pose_result_writeback_ok: bool = False
    last_inference_latency_ms: float | None = None
    lock_wait_avg_ms: float | None = None
    lock_wait_p95_ms: float | None = None
    last_lock_wait_ms: float | None = None
    slow_inference_count: int = 0
    skipped_due_to_busy: int = 0
    pose_skip_reasons: dict[str, int] | None = None
    last_target_track_id: int | None = None
    last_target_confidence: float | None = None
    last_bbox: list[float] | None = None
    last_pose_error: str | None = None
    last_pose_started_at: str | None = None
    last_pose_completed_at: str | None = None
    circuit_open: bool = False
    circuit_cooldown_remaining_ms: float | None = None
    last_error: str | None = None


class BehaviorStatus(BaseModel):
    enabled: bool = False
    state: str = "unknown"
    last_error: str | None = None


class TemporalStatus(BaseModel):
    enabled: bool = False
    feature_extractor_ok: bool = True
    window_size: int = 32
    active_tracks: int = 0
    fall_state: str = "normal"
    fall_probability: float = 0.0
    risk_level: str = "low"
    last_error: str | None = None


class PipelineStatus(BaseModel):
    detection_worker_fps: float = 0.0
    tracking_worker_fps: float = 0.0
    result_publish_fps: float = 0.0
    latest_detection_age_ms: float | None = None
    latest_tracking_age_ms: float | None = None
    latest_pose_age_ms: float | None = None
    detection_to_publish_lag_ms: float | None = None
    capture_queue_size: int | None = None
    detection_queue_size: int | None = None
    tracking_queue_size: int | None = None
    pose_queue_size: int | None = None
    publish_queue_size: int | None = None
    dropped_frames: int = 0
    last_error: str | None = None


class VisionStatus(BaseModel):
    service_status: str = "running"
    service_state: str = "normal"
    cameras: list[CameraStatus] = Field(default_factory=list)
    main_stream: StreamRuntimeStatus = Field(default_factory=StreamRuntimeStatus)
    analysis_stream: StreamRuntimeStatus = Field(default_factory=StreamRuntimeStatus)
    display_source: str = "single"
    analysis_source: str = "single"
    display_source_current: str = "single"
    display_fallback_active: bool = False
    detection: list[DetectionStatus] = Field(default_factory=list)
    streaming: StreamingStatus = Field(default_factory=StreamingStatus)
    workers: WorkerStatusGroup = Field(default_factory=WorkerStatusGroup)
    diagnostics: DiagnosticsStatus = Field(default_factory=DiagnosticsStatus)
    watchdog: WatchdogStatus = Field(default_factory=WatchdogStatus)
    tracking: TrackingStatus = Field(default_factory=TrackingStatus)
    identity: IdentityStatus = Field(default_factory=IdentityStatus)
    pose: PoseStatus = Field(default_factory=PoseStatus)
    behavior: BehaviorStatus = Field(default_factory=BehaviorStatus)
    temporal: TemporalStatus = Field(default_factory=TemporalStatus)
    pipeline: PipelineStatus = Field(default_factory=PipelineStatus)
