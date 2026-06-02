from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.vision_result import VisionResult


class ResultPullResponse(BaseModel):
    ok: bool = True
    camera_id: str
    has_result: bool
    result: VisionResult | None = None
    message: str = "ok"


class ResultPullListResponse(BaseModel):
    ok: bool = True
    count: int = Field(default=0, ge=0)
    results: list[VisionResult] = Field(default_factory=list)
    message: str = "ok"


class ManualFallEventRequest(BaseModel):
    camera_id: str = "camera_01"
    stream_name: str = "analysis"
    source: str = "vision_demo_manual_risk"
    event_type: str = "fall_risk_detected"
    state: str = "suspected_fall"
    risk: str = "medium"
    fall_prob: float | None = Field(default=0.72, ge=0, le=1)
    fall_score: float | None = Field(default=None, ge=0, le=1)
    track_id: str | None = None
    incident_id: str | None = None
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    snapshot_url: str | None = None
    timestamp: str | None = None
    demo: bool = True
    metadata: dict[str, Any] = Field(
        default_factory=lambda: {
            "trigger": "video_demo_button",
            "operator": "manual_test",
            "display_label": "疑似风险告警",
        }
    )


class ManualFallEventResponse(BaseModel):
    ok: bool = True
    accepted: bool = False
    forwarded: bool = False
    alarm_id: str | None = None
    alarm_type: str | None = None
    device_mac: str | None = None
    pushed: bool | None = None
    upstream_status_code: int | None = None
    main_system_url: str
    payload: dict[str, Any] = Field(default_factory=dict)
    main_system_response: dict[str, Any] | list[Any] | str | None = None
    message: str = "ok"
