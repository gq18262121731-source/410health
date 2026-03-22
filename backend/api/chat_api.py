from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from backend.dependencies import get_agent_service, get_stream_service
from backend.models.care_model import AgentDeviceHealthReport
from backend.models.user_model import UserRole


router = APIRouter(prefix="/chat", tags=["chat"])


class DeviceAnalysisRequest(BaseModel):
    device_mac: str
    question: str = Field(default="请结合最近监测数据给出离线健康分析。", min_length=4)
    role: UserRole = UserRole.FAMILY
    mode: str = Field(default="local", pattern="^local$")
    history_limit: int = Field(default=120, ge=12, le=1000)
    history_minutes: int = Field(default=1440, ge=30, le=43200)


class CommunityAnalysisRequest(BaseModel):
    question: str = Field(default="请结合社区多设备最近监测数据给出离线汇总分析。", min_length=4)
    role: UserRole = UserRole.COMMUNITY
    mode: str = Field(default="local", pattern="^local$")
    history_minutes: int = Field(default=1440, ge=30, le=43200)
    per_device_limit: int = Field(default=240, ge=12, le=1000)
    device_macs: list[str] = Field(default_factory=list)


class DeviceHealthReportRequest(BaseModel):
    device_mac: str
    start_at: datetime
    end_at: datetime
    role: UserRole = UserRole.FAMILY
    mode: str = Field(default="local", pattern="^local$")

    @model_validator(mode="after")
    def validate_window(self) -> "DeviceHealthReportRequest":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        return self


@router.post("/analyze")
async def analyze_health(payload: DeviceAnalysisRequest) -> dict[str, object]:
    recent = get_stream_service().recent_in_window(
        payload.device_mac,
        minutes=payload.history_minutes,
        limit=payload.history_limit,
    )
    return get_agent_service().analyze_device(
        role=payload.role,
        question=payload.question,
        samples=recent,
        mode=payload.mode,
    )


@router.post("/analyze/device")
async def analyze_device(payload: DeviceAnalysisRequest) -> dict[str, object]:
    return await analyze_health(payload)


@router.post("/analyze/community")
async def analyze_community(payload: CommunityAnalysisRequest) -> dict[str, object]:
    histories = get_stream_service().recent_by_devices(
        payload.device_macs or None,
        minutes=payload.history_minutes,
        per_device_limit=payload.per_device_limit,
    )
    return get_agent_service().analyze_community(
        role=payload.role,
        question=payload.question,
        device_samples=histories,
        mode=payload.mode,
    )


@router.post("/report/device", response_model=AgentDeviceHealthReport)
async def generate_device_health_report(payload: DeviceHealthReportRequest) -> AgentDeviceHealthReport:
    samples = [
        sample
        for sample in get_stream_service().recent(payload.device_mac, limit=1000)
        if payload.start_at <= sample.timestamp <= payload.end_at
    ]
    report = get_agent_service().generate_device_health_report(
        role=payload.role,
        device_mac=payload.device_mac,
        start_at=payload.start_at.astimezone(timezone.utc),
        end_at=payload.end_at.astimezone(timezone.utc),
        samples=samples,
        mode=payload.mode,
    )
    return AgentDeviceHealthReport.model_validate(report)


@router.get("/capabilities")
async def get_chat_capabilities() -> dict[str, object]:
    return get_agent_service().capability_report()


@router.get("/mcp-tools")
async def get_mcp_tool_specs() -> dict[str, object]:
    report = get_agent_service().capability_report()
    return {
        "mcp_connected": report.get("extensions", {}).get("mcp_connected", False),
        "tools": report.get("tool_specs", []),
    }
