from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.models.health_model import HealthSample
from backend.models.user_model import UserRole


class CommunityProfile(BaseModel):
    id: str
    name: str
    address: str
    manager: str
    hotline: str


class ElderProfile(BaseModel):
    id: str
    name: str
    age: int = Field(ge=50, le=120)
    apartment: str
    community_id: str
    device_mac: str
    device_macs: list[str] = Field(default_factory=list)
    family_ids: list[str] = Field(default_factory=list)


class FamilyProfile(BaseModel):
    id: str
    name: str
    relationship: str
    phone: str
    community_id: str
    elder_ids: list[str] = Field(default_factory=list)
    login_username: str


class CareDirectory(BaseModel):
    community: CommunityProfile
    elders: list[ElderProfile] = Field(default_factory=list)
    families: list[FamilyProfile] = Field(default_factory=list)


class CareFeatureAccess(BaseModel):
    basic_advice: bool = True
    device_metrics: bool = False
    health_evaluation: bool = False
    health_report: bool = False


class CareAccessDeviceMetric(BaseModel):
    device_mac: str
    device_name: str
    device_status: str
    bind_status: str
    elder_id: str | None = None
    elder_name: str | None = None
    latest_sample: HealthSample | None = None


class CareHealthReportSummary(BaseModel):
    device_mac: str
    risk_level: str
    sample_count: int
    latest_health_score: int | None = None
    recommendations: list[str] = Field(default_factory=list)
    notable_events: list[str] = Field(default_factory=list)


class CareHealthEvaluationSummary(BaseModel):
    device_mac: str
    risk_level: str
    risk_flags: list[str] = Field(default_factory=list)
    latest_health_score: int | None = None


class AgentReportPeriod(BaseModel):
    start_at: str
    end_at: str
    duration_minutes: int
    sample_count: int


class AgentMetricReportItem(BaseModel):
    latest: int | float | None = None
    average: float | None = None
    min: int | float | None = None
    max: int | float | None = None
    trend: str | None = None


class AgentDeviceHealthReport(BaseModel):
    report_type: str = "device_health_report"
    device_mac: str
    subject_name: str | None = None
    device_name: str | None = None
    generated_at: str
    period: AgentReportPeriod
    summary: str
    risk_level: str
    risk_flags: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metrics: dict[str, AgentMetricReportItem] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)


class CareAccessProfile(BaseModel):
    user_id: str
    role: UserRole
    community_id: str
    family_id: str | None = None
    binding_state: Literal["bound", "unbound", "not_applicable"]
    bound_device_macs: list[str] = Field(default_factory=list)
    related_elder_ids: list[str] = Field(default_factory=list)
    capabilities: CareFeatureAccess
    basic_advice: str
    device_metrics: list[CareAccessDeviceMetric] = Field(default_factory=list)
    health_evaluations: list[CareHealthEvaluationSummary] = Field(default_factory=list)
    health_reports: list[CareHealthReportSummary] = Field(default_factory=list)
