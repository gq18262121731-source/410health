from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException

from backend.dependencies import (
    get_alarm_service,
    get_care_service,
    get_data_analysis_service,
    get_device_service,
    get_display_latest_sample,
    get_effective_device_ingest_mode,
    get_relation_service,
    get_score_repo,
    get_stream_service,
    get_user_service,
    require_session_user,
)
from backend.models.auth_model import SessionUser
from backend.models.care_model import (
    CareAccessDeviceMetric,
    CareAccessProfile,
    CareDirectory,
    CommunityDashboardAlertItem,
    CommunityDashboardDeviceItem,
    CommunityDashboardElderItem,
    CommunityDashboardMetrics,
    CommunityDashboardSummary,
    CommunityDashboardTrendPoint,
    CommunityRelationTopology,
    CareFeatureAccess,
    CareHealthEvaluationSummary,
    CareHealthReportSummary,
    RelationTopologyLane,
    RelationTopologyNode,
    StructuredHealthInsight,
)
from backend.models.alarm_model import AlarmRecord, AlarmType
from backend.models.device_model import DeviceRecord
from backend.models.user_model import UserRole


router = APIRouter(prefix="/care", tags=["care"])


def _require_authenticated_user(authorization: str | None) -> SessionUser:
    try:
        return require_session_user(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _require_community_viewer(authorization: str | None) -> SessionUser:
    user = _require_authenticated_user(authorization)
    if user.role not in {UserRole.COMMUNITY, UserRole.ADMIN}:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    return user


def _user_bound_devices(user: SessionUser) -> tuple[list[str], list[DeviceRecord]]:
    device_service = get_device_service()
    relation_service = get_relation_service()
    care_service = get_care_service()
    devices = device_service.list_devices()

    if user.role == UserRole.ELDER:
        bound_devices = [device for device in devices if device.user_id == user.id]
        if bound_devices:
            return [user.id], bound_devices

        demo_directory = care_service.get_demo_directory()
        demo_elder = next((elder for elder in demo_directory.elders if elder.id == user.id), None)
        if demo_elder is None:
            return [user.id], []

        demo_device_macs = demo_elder.device_macs or ([demo_elder.device_mac] if demo_elder.device_mac else [])
        demo_devices = [device for device in devices if device.mac_address in demo_device_macs]
        return [demo_elder.id], demo_devices

    if user.role == UserRole.FAMILY:
        elder_ids = [
            relation.elder_user_id
            for relation in relation_service.list_relations_by_family(user.id)
            if relation.status == "active"
        ]
        bound_devices = [device for device in devices if device.user_id in elder_ids]
        if elder_ids or bound_devices:
            return elder_ids, bound_devices

        demo_directory = care_service.get_demo_directory()
        family_key = user.family_id or user.id
        demo_family = next((family for family in demo_directory.families if family.id == family_key), None)
        if demo_family is None:
            return [], []

        demo_elders_by_id = {elder.id: elder for elder in demo_directory.elders}
        demo_device_macs: set[str] = set()
        for elder_id in demo_family.elder_ids:
            elder = demo_elders_by_id.get(elder_id)
            if elder is None:
                continue
            demo_device_macs.update(elder.device_macs or ([elder.device_mac] if elder.device_mac else []))
        demo_devices = [device for device in devices if device.mac_address in demo_device_macs]
        return list(demo_family.elder_ids), demo_devices

    return [], []


def _basic_advice(user: SessionUser, binding_state: str) -> str:
    if user.role not in {UserRole.ELDER, UserRole.FAMILY}:
        return "当前账号属于运营或管理视角，用户态绑定建议不适用。"
    if binding_state == "bound":
        return "当前账号已绑定到有效设备链路，可查看设备指标、评估结果和健康报告摘要。"
    return "当前账号尚未绑定有效设备，先提供基础健康建议；完成设备绑定后可解锁实时指标、评估结果和健康报告。"


def _device_metrics(devices: list[DeviceRecord]) -> list[CareAccessDeviceMetric]:
    user_service = get_user_service()
    demo_directory = get_care_service().get_demo_directory()
    stream_service = get_stream_service()
    demo_elder_by_device_mac = {}
    for elder in demo_directory.elders:
        for mac in elder.device_macs or ([elder.device_mac] if elder.device_mac else []):
            if mac:
                demo_elder_by_device_mac[mac] = elder

    metrics: list[CareAccessDeviceMetric] = []
    for device in sorted(devices, key=lambda item: item.created_at):
        elder = user_service.get_user(device.user_id) if device.user_id else None
        demo_elder = demo_elder_by_device_mac.get(device.mac_address)
        metrics.append(
            CareAccessDeviceMetric(
                device_mac=device.mac_address,
                device_name=device.device_name,
                device_status=device.status,
                activation_state=device.activation_state,
                bind_status=device.bind_status,
                elder_id=elder.id if elder else getattr(demo_elder, "id", None),
                elder_name=elder.name if elder else getattr(demo_elder, "name", None),
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


def _sample_health_risk_reasons(
    *,
    device_status: str,
    latest_health_score: int | None,
    heart_rate: int | None,
    blood_oxygen: int | None,
    temperature: float | None,
    sos_flag: bool,
    active_alarm_count: int,
) -> tuple[str, int, list[str]]:
    reasons: list[str] = []
    score = 0

    if device_status == "pending":
        score += 8
        reasons.append("设备已注册，等待串口采集器收到首个实时包")
    elif device_status == "offline":
        score += 90
        reasons.append("设备离线，无法持续获取最新健康数据")
    elif device_status == "warning":
        score += 25
        reasons.append("设备状态异常，需要核查链路稳定性")

    if sos_flag:
        score += 120
        reasons.append("老人触发了 SOS 求助")

    if active_alarm_count:
        score += min(active_alarm_count * 18, 54)
        reasons.append(f"当前仍有 {active_alarm_count} 条活动告警未闭环")

    if latest_health_score is not None:
        if latest_health_score <= 60:
            score += 55
            reasons.append("最新健康评分低于 60 分")
        elif latest_health_score <= 75:
            score += 28
            reasons.append("最新健康评分处于关注区间")
    else:
        score += 15
        reasons.append("尚未形成可用的健康评分")

    if heart_rate is not None:
        if heart_rate < 45 or heart_rate > 180:
            score += 70
            reasons.append("心率出现重度异常")
        elif heart_rate < 55 or heart_rate > 120:
            score += 30
            reasons.append("心率波动超出稳态范围")

    if blood_oxygen is not None:
        if blood_oxygen < 90:
            score += 80
            reasons.append("血氧明显偏低")
        elif blood_oxygen < 93:
            score += 35
            reasons.append("血氧轻度偏低")

    if temperature is not None:
        if temperature >= 38.5:
            score += 55
            reasons.append("体温达到高热阈值")
        elif temperature >= 37.6:
            score += 22
            reasons.append("体温偏高，需要观察")

    if score >= 90:
        return "high", score, reasons
    if score >= 40:
        return "medium", score, reasons
    return "low", score, reasons


def _build_dashboard_trend(
    alarms: list[AlarmRecord],
    visible_device_macs: set[str],
) -> list[CommunityDashboardTrendPoint]:
    history_by_device = get_stream_service().recent_by_devices(
        device_macs=sorted(visible_device_macs),
        minutes=12 * 60,
        per_device_limit=144,
    )
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    score_buckets: dict[datetime, list[int]] = defaultdict(list)
    high_risk_buckets: dict[datetime, set[str]] = defaultdict(set)
    alert_buckets: Counter[datetime] = Counter()

    for mac, samples in history_by_device.items():
        for sample in samples:
            bucket = sample.timestamp.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
            if sample.health_score is not None:
                score_buckets[bucket].append(sample.health_score)
            if (
                sample.sos_flag
                or sample.heart_rate < 45
                or sample.heart_rate > 180
                or sample.blood_oxygen < 90
                or sample.temperature >= 38.5
                or (sample.health_score is not None and sample.health_score <= 60)
            ):
                high_risk_buckets[bucket].add(mac)

    for alarm in alarms:
        bucket = alarm.created_at.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        alert_buckets[bucket] += 1

    trend: list[CommunityDashboardTrendPoint] = []
    for offset in range(11, -1, -1):
        bucket = now - timedelta(hours=offset)
        scores = score_buckets.get(bucket, [])
        trend.append(
            CommunityDashboardTrendPoint(
                timestamp=bucket,
                average_health_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
                alert_count=alert_buckets.get(bucket, 0),
                high_risk_count=len(high_risk_buckets.get(bucket, set())),
            )
        )
    return trend


def _structured_payload_to_insight(payload: dict[str, object] | None) -> StructuredHealthInsight | None:
    if not payload:
        return None
    timestamp = payload.get("timestamp")
    evaluated_at: datetime | None = None
    if isinstance(timestamp, datetime):
        evaluated_at = timestamp
    elif isinstance(timestamp, str) and timestamp.strip():
        evaluated_at = datetime.fromisoformat(timestamp)
    active_events = payload.get("active_events")
    active_event_count = len(active_events) if isinstance(active_events, list) else 0
    abnormal_tags = payload.get("abnormal_tags")
    trigger_reasons = payload.get("trigger_reasons")
    return StructuredHealthInsight(
        evaluated_at=evaluated_at,
        health_score=float(payload["health_score"]) if payload.get("health_score") is not None else None,
        rule_health_score=(
            float(payload["rule_health_score"]) if payload.get("rule_health_score") is not None else None
        ),
        model_health_score=(
            float(payload["model_health_score"]) if payload.get("model_health_score") is not None else None
        ),
        risk_level=str(payload["risk_level"]) if payload.get("risk_level") else None,
        abnormal_tags=[str(item) for item in abnormal_tags] if isinstance(abnormal_tags, list) else [],
        trigger_reasons=[str(item) for item in trigger_reasons] if isinstance(trigger_reasons, list) else [],
        active_event_count=active_event_count,
        recommendation_code=str(payload["recommendation_code"]) if payload.get("recommendation_code") else None,
        score_adjustment_reason=(
            str(payload["score_adjustment_reason"]) if payload.get("score_adjustment_reason") else None
        ),
    )


def _dashboard_risk_from_structured(insight: StructuredHealthInsight | None, fallback: str) -> str:
    if insight is None or not insight.risk_level:
        return fallback
    if insight.risk_level in {"critical", "warning"}:
        return "high"
    if insight.risk_level == "attention":
        return "medium"
    if insight.risk_level == "normal":
        return "low"
    return fallback


def _dashboard_reasons_from_structured(insight: StructuredHealthInsight | None, fallback: list[str]) -> list[str]:
    if insight is None:
        return fallback
    if insight.trigger_reasons:
        return insight.trigger_reasons
    if insight.abnormal_tags:
        return insight.abnormal_tags
    return fallback


def _build_relation_topology(
    directory,
    devices: list[DeviceRecord],
    structured_by_device: dict[str, StructuredHealthInsight],
) -> CommunityRelationTopology:
    family_by_id = {family.id: family for family in directory.families}
    devices_by_user: dict[str, list[DeviceRecord]] = defaultdict(list)
    for device in devices:
        if device.user_id:
            devices_by_user[device.user_id].append(device)

    lanes: list[RelationTopologyLane] = []
    bound_device_macs: set[str] = set()
    for elder in directory.elders:
        elder_devices = sorted(devices_by_user.get(elder.id, []), key=lambda item: item.created_at)
        if not elder_devices:
            elder_devices = [
                device for device in devices if device.mac_address in set(elder.device_macs or ([elder.device_mac] if elder.device_mac else []))
            ]
        for device in elder_devices:
            bound_device_macs.add(device.mac_address)

        elder_device_nodes: list[RelationTopologyNode] = []
        lane_risk = "low"
        for device in elder_devices:
            structured = structured_by_device.get(device.mac_address)
            normalized_risk = _dashboard_risk_from_structured(structured, "low")
            if normalized_risk == "high":
                lane_risk = "high"
            elif normalized_risk == "medium" and lane_risk != "high":
                lane_risk = "medium"
            elder_device_nodes.append(
                RelationTopologyNode(
                    id=device.mac_address,
                    kind="device",
                    label=device.device_name,
                    subtitle=device.mac_address,
                    status=f"{device.status.value} / {device.activation_state.value} / {device.bind_status.value}",
                    risk_level=normalized_risk,
                )
            )

        family_nodes = [
            RelationTopologyNode(
                id=family.id,
                kind="family",
                label=family.name,
                subtitle=family.relationship,
                status=family.login_username,
                risk_level=None,
            )
            for family_id in elder.family_ids
            if (family := family_by_id.get(family_id)) is not None
        ]
        lanes.append(
            RelationTopologyLane(
                elder=RelationTopologyNode(
                    id=elder.id,
                    kind="elder",
                    label=elder.name,
                    subtitle=elder.apartment,
                    status=f"{len(family_nodes)} family / {len(elder_device_nodes)} device",
                    risk_level=lane_risk,
                ),
                families=family_nodes,
                devices=elder_device_nodes,
            )
        )

    unassigned_devices = [
        RelationTopologyNode(
            id=device.mac_address,
            kind="device",
            label=device.device_name,
            subtitle=device.mac_address,
            status=f"{device.status.value} / {device.activation_state.value} / {device.bind_status.value}",
            risk_level=_dashboard_risk_from_structured(structured_by_device.get(device.mac_address), "low"),
        )
        for device in devices
        if device.mac_address not in bound_device_macs
    ]

    lanes.sort(key=lambda item: (item.elder.risk_level != "high", item.elder.risk_level != "medium", item.elder.label))
    return CommunityRelationTopology(
        community=RelationTopologyNode(
            id=directory.community.id,
            kind="community",
            label=directory.community.name,
            subtitle=directory.community.manager,
            status=directory.community.hotline,
            risk_level=None,
        ),
        lanes=lanes,
        unassigned_devices=unassigned_devices,
    )


def _dashboard_alarm_type_counts(alarms: list[AlarmRecord]) -> tuple[int, int, int]:
    active = [alarm for alarm in alarms if not alarm.acknowledged]
    sos_count = sum(1 for alarm in active if alarm.alarm_type == AlarmType.SOS)
    health_count = sum(
        1
        for alarm in active
        if alarm.alarm_type in {
            AlarmType.VITAL_CRITICAL,
            AlarmType.ZSCORE_WARNING,
            AlarmType.INTELLIGENT_ANOMALY,
            AlarmType.COMMUNITY_RISK,
        }
    )
    device_count = sum(1 for alarm in active if alarm.alarm_type == AlarmType.DEVICE_STATUS)
    return sos_count, health_count, device_count


def _device_status_sort_key(item: CommunityDashboardDeviceItem) -> tuple[int, int, str]:
    if item.sos_active:
        return (-1, 0, item.device_mac)
    if item.device_status == "pending":
        return (0, 0, item.device_mac)
    if item.risk_level == "high":
        return (1, 0, item.device_mac)
    if item.risk_level == "medium":
        return (2, 0, item.device_mac)
    if item.device_status == "warning":
        return (3, 0, item.device_mac)
    if item.device_status == "online":
        return (4, 0, item.device_mac)
    return (5, 0, item.device_mac)


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


@router.get("/community/dashboard", response_model=CommunityDashboardSummary)
async def get_community_dashboard(authorization: str | None = Header(default=None)) -> CommunityDashboardSummary:
    _require_community_viewer(authorization)

    directory = get_care_service().get_directory()
    devices = get_device_service().list_devices()
    alarms = get_alarm_service().list_alarms(active_only=False)
    structured_payloads = get_score_repo().get_latest_by_device_ids([device.mac_address for device in devices])
    structured_by_device = {
        device_id: insight
        for device_id, insight in (
            (device_id, _structured_payload_to_insight(payload))
            for device_id, payload in structured_payloads.items()
        )
        if insight is not None
    }
    latest_by_mac = {
        device.mac_address: get_display_latest_sample(device.mac_address, device.ingest_mode)
        for device in devices
    }

    family_names_by_id = {family.id: family.name for family in directory.families}
    elder_by_device_mac: dict[str, object] = {}
    elder_by_id = {elder.id: elder for elder in directory.elders}

    for elder in directory.elders:
        for mac in elder.device_macs or ([elder.device_mac] if elder.device_mac else []):
            if mac:
                elder_by_device_mac[mac] = elder

    active_alarm_counts = Counter(alarm.device_mac for alarm in alarms if not alarm.acknowledged)
    active_sos_by_mac: dict[str, AlarmRecord] = {}
    for alarm in sorted(alarms, key=lambda item: item.created_at, reverse=True):
        if alarm.acknowledged or alarm.alarm_type != AlarmType.SOS:
            continue
        active_sos_by_mac.setdefault(alarm.device_mac, alarm)
    visible_device_macs = {device.mac_address for device in devices}

    top_risk_elders: list[CommunityDashboardElderItem] = []
    device_statuses: list[CommunityDashboardDeviceItem] = []

    for elder in directory.elders:
        device_mac = next((mac for mac in elder.device_macs if mac), elder.device_mac or None)
        device = next((item for item in devices if item.mac_address == device_mac), None) if device_mac else None
        sample = latest_by_mac.get(device_mac) if device_mac else None
        active_alarm_count = active_alarm_counts.get(device_mac or "", 0)
        risk_level, risk_score, risk_reasons = _sample_health_risk_reasons(
            device_status=device.status.value if device else "unknown",
            latest_health_score=sample.health_score if sample else None,
            heart_rate=sample.heart_rate if sample else None,
            blood_oxygen=sample.blood_oxygen if sample else None,
            temperature=sample.temperature if sample else None,
            sos_flag=bool(sample.sos_flag) if sample else False,
            active_alarm_count=active_alarm_count,
        )
        structured = structured_by_device.get(device_mac or "")
        dashboard_risk_level = _dashboard_risk_from_structured(structured, risk_level)
        dashboard_reasons = _dashboard_reasons_from_structured(structured, risk_reasons)
        top_risk_elders.append(
            CommunityDashboardElderItem(
                elder_id=elder.id,
                elder_name=elder.name,
                apartment=elder.apartment,
                device_mac=device_mac,
                family_names=[family_names_by_id[family_id] for family_id in elder.family_ids if family_id in family_names_by_id],
                risk_level=dashboard_risk_level,
                risk_score=risk_score,
                risk_reasons=dashboard_reasons,
                device_status=device.status.value if device else "unknown",
                latest_timestamp=(
                    structured.evaluated_at
                    if structured and structured.evaluated_at
                    else (sample.timestamp if sample else device.last_seen_at if device else None)
                ),
                latest_health_score=(
                    int(round(structured.health_score)) if structured and structured.health_score is not None else (sample.health_score if sample else None)
                ),
                heart_rate=sample.heart_rate if sample else None,
                blood_oxygen=sample.blood_oxygen if sample else None,
                blood_pressure=sample.blood_pressure if sample else None,
                temperature=sample.temperature if sample else None,
                steps=sample.steps if sample else None,
                active_alarm_count=active_alarm_count,
                structured_health=structured,
            )
        )

    for device in devices:
        elder = elder_by_device_mac.get(device.mac_address)
        sample = latest_by_mac.get(device.mac_address)
        effective_ingest_mode = get_effective_device_ingest_mode(device.mac_address, device.ingest_mode)
        active_alarm_count = active_alarm_counts.get(device.mac_address, 0)
        risk_level, _, risk_reasons = _sample_health_risk_reasons(
            device_status=device.status.value,
            latest_health_score=sample.health_score if sample else None,
            heart_rate=sample.heart_rate if sample else None,
            blood_oxygen=sample.blood_oxygen if sample else None,
            temperature=sample.temperature if sample else None,
            sos_flag=bool(sample.sos_flag) if sample else False,
            active_alarm_count=active_alarm_count,
        )
        structured = structured_by_device.get(device.mac_address)
        dashboard_risk_level = _dashboard_risk_from_structured(structured, risk_level)
        dashboard_reasons = _dashboard_reasons_from_structured(structured, risk_reasons)
        active_sos_alarm = active_sos_by_mac.get(device.mac_address)
        device_statuses.append(
            CommunityDashboardDeviceItem(
                device_mac=device.mac_address,
                device_name=device.device_name,
                model_code=device.model_code,
                ingest_mode=effective_ingest_mode.value if effective_ingest_mode is not None else device.ingest_mode.value,
                service_uuid=device.service_uuid,
                device_uuid=device.device_uuid,
                elder_id=getattr(elder, "id", None),
                elder_name=getattr(elder, "name", None),
                apartment=getattr(elder, "apartment", None),
                device_status=device.status.value,
                activation_state=device.activation_state.value,
                bind_status=device.bind_status.value,
                risk_level=dashboard_risk_level,
                risk_reasons=dashboard_reasons,
                latest_timestamp=(
                    structured.evaluated_at
                    if structured and structured.evaluated_at
                    else (sample.timestamp if sample else device.last_seen_at)
                ),
                last_seen_at=device.last_seen_at,
                last_packet_type=device.last_packet_type,
                latest_health_score=(
                    int(round(structured.health_score)) if structured and structured.health_score is not None else (sample.health_score if sample else None)
                ),
                heart_rate=sample.heart_rate if sample else None,
                blood_oxygen=sample.blood_oxygen if sample else None,
                blood_pressure=sample.blood_pressure if sample else None,
                temperature=sample.temperature if sample else None,
                battery=sample.battery if sample else None,
                steps=sample.steps if sample else None,
                active_alarm_count=active_alarm_count,
                sos_active=active_sos_alarm is not None,
                active_sos_alarm_id=active_sos_alarm.id if active_sos_alarm else None,
                active_sos_trigger=(
                    str(active_sos_alarm.metadata.get("sos_trigger"))
                    if active_sos_alarm and active_sos_alarm.metadata.get("sos_trigger")
                    else None
                ),
                structured_health=structured,
            )
        )

    recent_alerts = sorted(alarms, key=lambda alarm: alarm.created_at, reverse=True)[:8]
    dashboard_alerts = [
        CommunityDashboardAlertItem(
            alarm_id=alarm.id,
            device_mac=alarm.device_mac,
            elder_name=getattr(elder_by_device_mac.get(alarm.device_mac), "name", None),
            apartment=getattr(elder_by_device_mac.get(alarm.device_mac), "apartment", None),
            alarm_type=alarm.alarm_type.value,
            alarm_layer=alarm.alarm_layer.value,
            alarm_level=int(alarm.alarm_level.value),
            message=alarm.message,
            created_at=alarm.created_at,
            acknowledged=alarm.acknowledged,
        )
        for alarm in recent_alerts
    ]

    health_scores = [item.latest_health_score for item in device_statuses if item.latest_health_score is not None]
    blood_oxygen_values = [item.blood_oxygen for item in device_statuses if item.blood_oxygen is not None]
    now = datetime.now(timezone.utc)
    today_alarm_count = sum(1 for alarm in alarms if alarm.created_at.astimezone(timezone.utc).date() == now.date())
    sos_alarm_count, health_alert_count, device_alert_count = _dashboard_alarm_type_counts(alarms)
    last_sync_at = max((item.latest_timestamp for item in device_statuses if item.latest_timestamp), default=None)

    metrics = CommunityDashboardMetrics(
        elder_count=len(directory.elders),
        family_count=len(directory.families),
        device_total=len(devices),
        device_pending=sum(1 for device in devices if device.status.value == "pending"),
        device_online=sum(1 for device in devices if device.status.value == "online"),
        device_offline=sum(1 for device in devices if device.status.value == "offline"),
        active_alarm_count=sum(1 for alarm in alarms if not alarm.acknowledged),
        unacknowledged_alarm_count=sum(1 for alarm in alarms if not alarm.acknowledged),
        sos_alarm_count=sos_alarm_count,
        health_alert_count=health_alert_count,
        device_alert_count=device_alert_count,
        high_risk_elder_count=sum(1 for elder in top_risk_elders if elder.risk_level == "high"),
        average_health_score=round(sum(health_scores) / len(health_scores), 1) if health_scores else 0.0,
        average_blood_oxygen=round(sum(blood_oxygen_values) / len(blood_oxygen_values), 1)
        if blood_oxygen_values
        else 0.0,
        today_alarm_count=today_alarm_count,
        last_sync_at=last_sync_at,
    )

    return CommunityDashboardSummary(
        community=directory.community,
        metrics=metrics,
        top_risk_elders=sorted(
            top_risk_elders,
            key=lambda item: (item.risk_level != "high", item.risk_level != "medium", -item.risk_score),
        )[:10],
        device_statuses=sorted(
            device_statuses,
            key=_device_status_sort_key,
        ),
        recent_alerts=dashboard_alerts,
        trend=_build_dashboard_trend(alarms, visible_device_macs),
        relation_topology=_build_relation_topology(directory, devices, structured_by_device),
    )
