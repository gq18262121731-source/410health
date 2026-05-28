from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ServiceState = Literal["mock", "starting", "running", "degraded", "stopped", "error", "unknown"]
VideoStreamType = Literal["ws_image", "mjpeg", "hls", "webrtc", "flv", "snapshot", "unknown"]
FallState = Literal["unknown", "normal", "suspected_fall", "confirmed_fall", "fallen", "recovery", "error"]
RiskLevel = Literal["unknown", "low", "medium", "high", "critical"]


class VideoAnalysisTarget(BaseModel):
    target_id: str | None = None
    label: str | None = None
    matched: bool | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VideoAnalysisPushRequest(BaseModel):
    """Payload accepted from a future standalone video analysis service.

    The model intentionally stays independent from the legacy camera/pose/fall
    runtime. Extra keys are preserved in `metadata` so the future service can
    evolve without forcing a main-system release for every telemetry addition.
    """

    model_config = ConfigDict(extra="allow")

    camera_id: str = Field(..., min_length=1, max_length=80)
    stream_name: str = Field(default="primary", max_length=80)
    service_state: ServiceState = "running"
    camera_lost: bool = False
    capture_stale: bool = False
    frame_age_ms: int | None = Field(default=None, ge=0)
    video_fps: float | None = Field(default=None, ge=0.0)
    overlay_fps: float | None = Field(default=None, ge=0.0)
    ws_fps: float | None = Field(default=None, ge=0.0)
    stream_type: VideoStreamType = "ws_image"
    stream_url: str | None = Field(default=None, max_length=1024)
    track_id: str | None = Field(default=None, max_length=120)
    bbox: list[float] | None = None
    target: VideoAnalysisTarget | dict[str, Any] | str | None = None
    fall_state: FallState = "unknown"
    risk: RiskLevel = "unknown"
    fall_prob: float | None = Field(default=None, ge=0.0, le=1.0)
    snapshot_url: str | None = Field(default=None, max_length=1024)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if len(value) != 4:
            raise ValueError("bbox must contain [x1, y1, x2, y2]")
        return [float(item) for item in value]

    @field_validator("stream_name")
    @classmethod
    def normalize_stream_name(cls, value: str) -> str:
        stripped = value.strip()
        return stripped or "primary"


class VideoAnalysisRecord(VideoAnalysisPushRequest):
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stale: bool = False
    adapter_version: str = "video_adapter.v1"


class VideoAnalysisIngestResponse(BaseModel):
    ok: bool = True
    accepted: bool = True
    camera_id: str
    stream_name: str
    received_at: datetime
    service_state: ServiceState
    stale: bool


class VideoBridgeStatusResponse(BaseModel):
    ok: bool = True
    bridge_state: ServiceState
    adapter_version: str
    camera_count: int
    updated_at: datetime
    latest: VideoAnalysisRecord | None = None
    cameras: list[VideoAnalysisRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
