from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FallState(StrEnum):
    NORMAL = "normal"
    UNSTABLE = "unstable"
    FALLING = "falling"
    FALLEN_CANDIDATE = "fallen_candidate"
    FALLEN_CONFIRMED = "fallen_confirmed"
    COOLDOWN = "cooldown"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    COOLDOWN = "cooldown"


class TargetFeature(BaseModel):
    track_id: int | None = None
    timestamp: str
    monotonic_time: float
    bbox_center_x: float = 0.0
    bbox_center_y: float = 0.0
    bbox_width: float = 0.0
    bbox_height: float = 0.0
    aspect_ratio: float = 0.0
    delta_x: float = 0.0
    delta_y: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    speed: float = 0.0
    pose_available: bool = False
    pose_confidence: float = 0.0
    torso_angle: float | None = None
    hip_height_ratio: float | None = None
    head_height_ratio: float | None = None


class SequencePrediction(BaseModel):
    source: str = "mock"
    fall_probability: float = Field(ge=0.0, le=1.0)


class FallDecision(BaseModel):
    fall_state: str = FallState.NORMAL.value
    risk_level: str = RiskLevel.LOW.value
    countdown_ms: int = 0


class TemporalStatus(BaseModel):
    enabled: bool = False
    feature_extractor_ok: bool = True
    window_size: int = 32
    active_tracks: int = 0
    fall_state: str = FallState.NORMAL.value
    fall_probability: float = 0.0
    risk_level: str = RiskLevel.LOW.value
    last_error: str | None = None
