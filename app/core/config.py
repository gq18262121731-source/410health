from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "vision-service")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    default_camera_id: str = os.getenv("DEFAULT_CAMERA_ID", "camera_01")
    default_rtsp_url: str | None = os.getenv("DEFAULT_RTSP_URL") or None
    enable_dual_stream: bool = _get_bool("ENABLE_DUAL_STREAM", False)
    main_stream_url: str | None = os.getenv("MAIN_STREAM_URL") or None
    analysis_stream_url: str | None = os.getenv("ANALYSIS_STREAM_URL") or None
    main_capture_backend: str = os.getenv("MAIN_CAPTURE_BACKEND", "subprocess_opencv")
    analysis_capture_backend: str = os.getenv("ANALYSIS_CAPTURE_BACKEND", "subprocess_opencv")
    display_fallback_to_analysis: bool = _get_bool("DISPLAY_FALLBACK_TO_ANALYSIS", True)
    display_fallback_frame_age_ms: int = _get_int("DISPLAY_FALLBACK_FRAME_AGE_MS", 1500)
    display_fallback_min_hold_ms: int = _get_int("DISPLAY_FALLBACK_MIN_HOLD_MS", 10000)
    mock_camera_enabled: bool = _get_bool("MOCK_CAMERA_ENABLED", True)
    mock_camera_width: int = _get_int("MOCK_CAMERA_WIDTH", 1280)
    mock_camera_height: int = _get_int("MOCK_CAMERA_HEIGHT", 720)
    mock_camera_fps: int = _get_int("MOCK_CAMERA_FPS", 25)

    capture_stale_timeout_sec: float = _get_float("CAPTURE_STALE_TIMEOUT_SEC", 3.0)
    stream_stale_threshold_ms: int = _get_int("STREAM_STALE_THRESHOLD_MS", 3000)
    stream_stale_reconnect_after_ms: int = _get_int("STREAM_STALE_RECONNECT_AFTER_MS", 6000)
    capture_read_warn_ms: int = _get_int("CAPTURE_READ_WARN_MS", 500)
    capture_read_stale_ms: int = _get_int("CAPTURE_READ_STALE_MS", 3000)
    capture_force_reopen_after_slow_reads: int = _get_int("CAPTURE_FORCE_REOPEN_AFTER_SLOW_READS", 3)
    capture_read_watchdog_release_enabled: bool = _get_bool("CAPTURE_READ_WATCHDOG_RELEASE_ENABLED", False)
    capture_backend: str = os.getenv("CAPTURE_BACKEND", "opencv")
    capture_process_frame_timeout_ms: int = _get_int("CAPTURE_PROCESS_FRAME_TIMEOUT_MS", 2000)
    capture_process_restart_ms: int = _get_int("CAPTURE_PROCESS_RESTART_MS", 500)
    capture_ipc_mode: str = os.getenv("CAPTURE_IPC_MODE", "jpeg_pipe")
    capture_jpeg_quality: int = _get_int("CAPTURE_JPEG_QUALITY", 60)
    capture_process_output_height: int = _get_int("CAPTURE_PROCESS_OUTPUT_HEIGHT", 720)
    capture_process_write_fps: float = _get_float("CAPTURE_PROCESS_WRITE_FPS", 10.0)
    main_capture_jpeg_quality: int = _get_int("MAIN_CAPTURE_JPEG_QUALITY", 55)
    main_capture_process_output_height: int = _get_int("MAIN_CAPTURE_PROCESS_OUTPUT_HEIGHT", 720)
    main_capture_process_write_fps: float = _get_float("MAIN_CAPTURE_PROCESS_WRITE_FPS", 8.0)
    capture_process_max_restarts: int = _get_int("CAPTURE_PROCESS_MAX_RESTARTS", 0)
    opencv_capture_buffersize: int = _get_int("OPENCV_CAPTURE_BUFFERSIZE", 1)
    opencv_ffmpeg_capture_options: str = os.getenv("OPENCV_FFMPEG_CAPTURE_OPTIONS", "")
    reconnect_initial_delay_sec: float = _get_float("RECONNECT_INITIAL_DELAY_SEC", 1.0)
    reconnect_max_delay_sec: float = _get_float("RECONNECT_MAX_DELAY_SEC", 10.0)

    detection_enabled: bool = _get_bool("DETECTION_ENABLED", True)
    yolo_model_path: str = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
    yolo_confidence: float = _get_float("YOLO_CONFIDENCE", 0.35)
    yolo_imgsz: int = _get_int("YOLO_IMGSZ", 512)
    yolo_device: str | None = os.getenv("YOLO_DEVICE") or None
    detection_interval_ms: int = _get_int("DETECTION_INTERVAL_MS", 200)

    enable_tracking: bool = _get_bool("ENABLE_TRACKING", True)
    enable_identity: bool = _get_bool("ENABLE_IDENTITY", False)
    enable_target_binding: bool = _get_bool("ENABLE_TARGET_BINDING", False)
    identity_store_dir: str = os.getenv("IDENTITY_STORE_DIR", "data/identities")
    identity_max_images: int = _get_int("IDENTITY_MAX_IMAGES", 5)
    insightface_model_name: str = os.getenv("INSIGHTFACE_MODEL_NAME", "buffalo_l")
    insightface_ctx_id: int = _get_int("INSIGHTFACE_CTX_ID", 0)
    insightface_det_size: int = _get_int("INSIGHTFACE_DET_SIZE", 640)
    insightface_providers: str | None = os.getenv("INSIGHTFACE_PROVIDERS") or None
    identity_service_url: str = os.getenv("IDENTITY_SERVICE_URL", "http://127.0.0.1:8100")
    enable_identity_binding: bool = _get_bool("ENABLE_IDENTITY_BINDING", False)
    identity_request_timeout_ms: int = _get_int("IDENTITY_REQUEST_TIMEOUT_MS", 500)
    identity_match_interval_ms: int = _get_int("IDENTITY_MATCH_INTERVAL_MS", 1000)
    identity_match_threshold: float = _get_float("IDENTITY_MATCH_THRESHOLD", 0.45)
    identity_crop_padding_ratio: float = _get_float("IDENTITY_CROP_PADDING_RATIO", 0.12)
    identity_binding_async: bool = _get_bool("IDENTITY_BINDING_ASYNC", True)
    identity_health_ttl_ms: int = _get_int("IDENTITY_HEALTH_TTL_MS", 5000)
    identity_match_ttl_ms: int = _get_int("IDENTITY_MATCH_TTL_MS", 1000)
    identity_binding_worker_fps: float = _get_float("IDENTITY_BINDING_WORKER_FPS", 1.0)
    identity_max_inflight: int = _get_int("IDENTITY_MAX_INFLIGHT", 1)
    target_lost_after_ms: int = _get_int("TARGET_LOST_AFTER_MS", 1000)
    target_reacquire_after_ms: int = _get_int("TARGET_REACQUIRE_AFTER_MS", 3000)
    bytetrack_track_high_thresh: float = _get_float("BYTETRACK_TRACK_HIGH_THRESH", 0.5)
    bytetrack_track_low_thresh: float = _get_float("BYTETRACK_TRACK_LOW_THRESH", 0.1)
    bytetrack_new_track_thresh: float = _get_float("BYTETRACK_NEW_TRACK_THRESH", 0.6)
    bytetrack_match_thresh: float = _get_float("BYTETRACK_MATCH_THRESH", 0.8)
    bytetrack_track_buffer: int = _get_int("BYTETRACK_TRACK_BUFFER", 30)
    bytetrack_frame_rate: int = _get_int("BYTETRACK_FRAME_RATE", 10)
    bytetrack_fuse_score: bool = _get_bool("BYTETRACK_FUSE_SCORE", True)

    enable_pose: bool = _get_bool("ENABLE_POSE", False)
    pose_provider: str = os.getenv("POSE_PROVIDER", "mock")
    pose_fps: float = _get_float("POSE_FPS", 3.0)
    yolo_pose_model_path: str = os.getenv("YOLO_POSE_MODEL_PATH", "yolov8n-pose.pt")
    yolo_pose_confidence: float = _get_float("YOLO_POSE_CONFIDENCE", 0.25)
    yolo_pose_imgsz: int = _get_int("YOLO_POSE_IMGSZ", 320)
    yolo_pose_device: str | None = os.getenv("YOLO_POSE_DEVICE") or None
    pose_target_only: bool = _get_bool("POSE_TARGET_ONLY", False)
    pose_fallback_to_largest_track: bool = _get_bool("POSE_FALLBACK_TO_LARGEST_TRACK", True)
    pose_fallback_to_detection: bool = _get_bool("POSE_FALLBACK_TO_DETECTION", True)
    pose_fallback_min_confidence: float = _get_float("POSE_FALLBACK_MIN_CONFIDENCE", 0.35)
    pose_crop_padding_ratio: float = _get_float("POSE_CROP_PADDING_RATIO", 0.08)
    pose_skip_when_inference_busy: bool = _get_bool("POSE_SKIP_WHEN_INFERENCE_BUSY", True)
    pose_max_inference_ms: int = _get_int("POSE_MAX_INFERENCE_MS", 1500)
    pose_slow_inference_circuit_breaker_count: int = _get_int("POSE_SLOW_INFERENCE_CIRCUIT_BREAKER_COUNT", 3)
    pose_circuit_breaker_cooldown_ms: int = _get_int("POSE_CIRCUIT_BREAKER_COOLDOWN_MS", 10000)

    enable_behavior: bool = _get_bool("ENABLE_BEHAVIOR", False)
    behavior_rapid_descent_px_per_sec: float = _get_float("BEHAVIOR_RAPID_DESCENT_PX_PER_SEC", 260.0)
    behavior_long_still_sec: float = _get_float("BEHAVIOR_LONG_STILL_SEC", 5.0)
    behavior_still_velocity_px_per_sec: float = _get_float("BEHAVIOR_STILL_VELOCITY_PX_PER_SEC", 18.0)

    tracking_worker_fps: float = _get_float("TRACKING_WORKER_FPS", 12.0)
    pose_worker_fps: float = _get_float("POSE_WORKER_FPS", 2.0)
    result_publish_fps: float = _get_float("RESULT_PUBLISH_FPS", 10.0)
    pose_result_ttl_ms: int = _get_int("POSE_RESULT_TTL_MS", 1500)
    behavior_result_ttl_ms: int = _get_int("BEHAVIOR_RESULT_TTL_MS", 1500)

    watchdog_enabled: bool = _get_bool("WATCHDOG_ENABLED", True)
    watchdog_check_interval_ms: int = _get_int("WATCHDOG_CHECK_INTERVAL_MS", 1000)
    watchdog_worker_heartbeat_timeout_ms: int = _get_int("WATCHDOG_WORKER_HEARTBEAT_TIMEOUT_MS", 5000)
    watchdog_capture_stale_ms: int = _get_int("WATCHDOG_CAPTURE_STALE_MS", 3000)
    watchdog_max_restart_count: int = _get_int("WATCHDOG_MAX_RESTART_COUNT", 3)
    watchdog_restart_window_ms: int = _get_int("WATCHDOG_RESTART_WINDOW_MS", 60000)

    video_bridge_enabled: bool = _get_bool("VIDEO_BRIDGE_ENABLED", False)
    video_bridge_url: str = os.getenv(
        "VIDEO_BRIDGE_URL",
        "http://127.0.0.1:8000/api/v1/video-bridge/analysis",
    )
    video_bridge_fall_event_url: str = os.getenv(
        "VIDEO_BRIDGE_FALL_EVENT_URL",
        "http://192.168.8.251:18080/api/v1/video-bridge/fall-events",
    )
    video_bridge_fps: float = _get_float("VIDEO_BRIDGE_FPS", 1.0)
    video_bridge_timeout_seconds: float = _get_float("VIDEO_BRIDGE_TIMEOUT_SECONDS", 2.0)

    enable_temporal: bool = _get_bool("ENABLE_TEMPORAL", False)
    feature_window_size: int = _get_int("FEATURE_WINDOW_SIZE", 32)
    unstable_frame_threshold: int = _get_int("UNSTABLE_FRAME_THRESHOLD", 3)
    falling_prob_threshold: float = _get_float("FALLING_PROB_THRESHOLD", 0.65)
    fall_confirm_frames: int = _get_int("FALL_CONFIRM_FRAMES", 5)
    fall_still_ms: int = _get_int("FALL_STILL_MS", 1500)
    cooldown_seconds: float = _get_float("COOLDOWN_SECONDS", 10.0)

    webrtc_stun_server: str = os.getenv(
        "WEBRTC_STUN_SERVER",
        "stun:stun.l.google.com:19302",
    )
    webrtc_video_fps: int = _get_int("WEBRTC_VIDEO_FPS", 25)


@lru_cache
def get_settings() -> Settings:
    return Settings()
