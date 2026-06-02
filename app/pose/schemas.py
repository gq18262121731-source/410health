from __future__ import annotations

from pydantic import BaseModel


class PoseKeypoint(BaseModel):
    name: str
    x: float
    y: float
    confidence: float


class PoseResult(BaseModel):
    track_id: int | None = None
    keypoints: list[PoseKeypoint]
    skeleton_confidence: float


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
