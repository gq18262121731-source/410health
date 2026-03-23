from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from backend.dependencies import (
    get_care_service,
    get_data_analysis_service,
    get_device_service,
    get_relation_service,
    get_stream_service,
    get_user_service,
    require_session_user,
)
from backend.models.auth_model import SessionUser
from backend.models.care_model import (
    CareAccessDeviceMetric,
    CareAccessProfile,
    CareDirectory,
    CareFeatureAccess,
    CareHealthEvaluationSummary,
    CareHealthReportSummary,
)
from backend.models.device_model import DeviceRecord
from backend.models.user_model import UserRole


router = APIRouter(prefix="/care", tags=["care"])


def _require_authenticated_user(authorization: str | None) -> SessionUser:
    try:
        return require_session_user(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _user_bound_devices(user: SessionUser) -> tuple[list[str], list[DeviceRecord]]:
    device_service = get_device_service()
    relation_service = get_relation_service()

    if user.role == UserRole.ELDER:
        devices = [device for device in device_service.list_devices() if device.user_id == user.id]
        return [user.id], devices

    if user.role == UserRole.FAMILY:
        elder_ids = [
            relation.elder_user_id
            for relation in relation_service.list_relations_by_family(user.id)
            if relation.status == "active"
        ]
        devices = [device for device in device_service.list_devices() if device.user_id in elder_ids]
        return elder_ids, devices

    return [], []


def _basic_advice(user: SessionUser, binding_state: str) -> str:
    if user.role not in {UserRole.ELDER, UserRole.FAMILY}:
        return "当前账号属于运营或管理视角，用户态绑定建议不适用。"
    if binding_state == "bound":
        return "当前账号已绑定到有效设备链路，可查看设备指标、评估结果和健康报告摘要。"
    return "当前账号尚未绑定有效设备，先提供基础健康建议；完成设备绑定后可解锁实时指标、评估结果和健康报告。"


def _device_metrics(devices: list[DeviceRecord]) -> list[CareAccessDeviceMetric]:
    user_service = get_user_service()
    stream_service = get_stream_service()
    metrics: list[CareAccessDeviceMetric] = []
    for device in sorted(devices, key=lambda item: item.created_at):
        elder = user_service.get_user(device.user_id) if device.user_id else None
        metrics.append(
            CareAccessDeviceMetric(
                device_mac=device.mac_address,
                device_name=device.device_name,
                device_status=device.status,
                bind_status=device.bind_status,
                elder_id=device.user_id,
                elder_name=elder.name if elder else None,
                latest_sample=stream_service.latest(device.mac_address),
            )
        )
    return metrics


def _health_reports(devices: list[DeviceRecord]) -> list[CareHealthReportSummary]:
    analysis_service = get_data_analysis_service()
    stream_service = get_stream_service()
    reports: list[CareHealthReportSummary] = []
    for device in sorted(devices, key=lambda item: item.created_at):
        summary = analysis_service.summarize_device(
            stream_service.recent_in_window(device.mac_address, minutes=1440, limit=240)
        )
        latest = summary.get("latest", {}) if isinstance(summary, dict) else {}
        if not isinstance(latest, dict):
            latest = {}
        reports.append(
            CareHealthReportSummary(
                device_mac=device.mac_address,
                risk_level=str(summary.get("risk_level", "unknown")),
                sample_count=int(summary.get("sample_count", 0)),
                latest_health_score=latest.get("health_score") if isinstance(latest.get("health_score"), int) else None,
                recommendations=[str(item) for item in summary.get("recommendations", [])[:3]],
                notable_events=[str(item) for item in summary.get("notable_events", [])[:3]],
            )
        )
    return reports


def _health_evaluations(devices: list[DeviceRecord]) -> list[CareHealthEvaluationSummary]:
    analysis_service = get_data_analysis_service()
    stream_service = get_stream_service()
    evaluations: list[CareHealthEvaluationSummary] = []
    for device in sorted(devices, key=lambda item: item.created_at):
        summary = analysis_service.summarize_device(
            stream_service.recent_in_window(device.mac_address, minutes=1440, limit=240)
        )
        latest = summary.get("latest", {}) if isinstance(summary, dict) else {}
        if not isinstance(latest, dict):
            latest = {}
        evaluations.append(
            CareHealthEvaluationSummary(
                device_mac=device.mac_address,
                risk_level=str(summary.get("risk_level", "unknown")),
                risk_flags=[str(item) for item in summary.get("risk_flags", [])],
                latest_health_score=latest.get("health_score") if isinstance(latest.get("health_score"), int) else None,
            )
        )
    return evaluations


@router.get("/directory", response_model=CareDirectory)
async def get_care_directory() -> CareDirectory:
    return get_care_service().get_directory()


@router.get("/directory/family/{family_id}", response_model=CareDirectory)
async def get_family_directory(family_id: str) -> CareDirectory:
    return get_care_service().get_family_directory(family_id)


@router.get("/access-profile/me", response_model=CareAccessProfile)
async def get_access_profile(authorization: str | None = Header(default=None)) -> CareAccessProfile:
    user = _require_authenticated_user(authorization)
    elder_ids, devices = _user_bound_devices(user)

    if user.role not in {UserRole.ELDER, UserRole.FAMILY}:
        return CareAccessProfile(
            user_id=user.id,
            role=user.role,
            community_id=user.community_id,
            family_id=user.family_id,
            binding_state="not_applicable",
            bound_device_macs=[],
            related_elder_ids=[],
            capabilities=CareFeatureAccess(
                basic_advice=False,
                device_metrics=False,
                health_evaluation=False,
                health_report=False,
            ),
            basic_advice=_basic_advice(user, "not_applicable"),
            device_metrics=[],
            health_evaluations=[],
            health_reports=[],
        )

    binding_state = "bound" if devices else "unbound"
    capabilities = CareFeatureAccess(
        basic_advice=True,
        device_metrics=bool(devices),
        health_evaluation=bool(devices),
        health_report=bool(devices),
    )
    return CareAccessProfile(
        user_id=user.id,
        role=user.role,
        community_id=user.community_id,
        family_id=user.family_id,
        binding_state=binding_state,
        bound_device_macs=[device.mac_address for device in devices],
        related_elder_ids=elder_ids,
        capabilities=capabilities,
        basic_advice=_basic_advice(user, binding_state),
        device_metrics=_device_metrics(devices) if devices else [],
        health_evaluations=_health_evaluations(devices) if devices else [],
        health_reports=_health_reports(devices) if devices else [],
    )
