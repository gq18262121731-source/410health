from __future__ import annotations

from pydantic import BaseModel, Field


class CameraStatus(BaseModel):
    camera_id: str
    running: bool
    connected: bool
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
    capture_ipc_decode_errors: int = 0
    capture_ipc_dropped_frames: int = 0
    capture_output_width: int | None = None
    capture_output_height: int | None = None
    last_error: str | None = None


class DetectionStatus(BaseModel):
    camera_id: str
    running: bool
    enabled: bool
    loaded: bool
    model_name: str | None = None
    detection_fps: float = 0.0
    inference_latency_ms: float | None = None
    last_error: str | None = None


class StreamingStatus(BaseModel):
    webrtc_clients: int = 0
    ws_clients: int = 0


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
    last_inference_latency_ms: float | None = None
    slow_inference_count: int = 0
    skipped_due_to_busy: int = 0
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
    last_error: str | None = None


class VisionStatus(BaseModel):
    service_status: str = "running"
    cameras: list[CameraStatus] = Field(default_factory=list)
    detection: list[DetectionStatus] = Field(default_factory=list)
    streaming: StreamingStatus = Field(default_factory=StreamingStatus)
    tracking: TrackingStatus = Field(default_factory=TrackingStatus)
    identity: IdentityStatus = Field(default_factory=IdentityStatus)
    pose: PoseStatus = Field(default_factory=PoseStatus)
    behavior: BehaviorStatus = Field(default_factory=BehaviorStatus)
    temporal: TemporalStatus = Field(default_factory=TemporalStatus)
    pipeline: PipelineStatus = Field(default_factory=PipelineStatus)
