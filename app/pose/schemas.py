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
    last_inference_latency_ms: float | None = None
    slow_inference_count: int = 0
    skipped_due_to_busy: int = 0
    circuit_open: bool = False
    circuit_cooldown_remaining_ms: float | None = None
    last_error: str | None = None
