from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime, timezone

from backend.dependencies import (
    _annotate_alarm_timeline,
    _enrich_alarm_metadata,
    _serialize_alarm_queue_items,
    get_alarm_service,
    get_care_service,
    get_health_data_repository,
    get_websocket_manager,
    require_session_user,
)
from backend.models.alarm_model import AlarmQueueItem, AlarmRecord, MobilePushRecord
from backend.models.user_model import UserRole


router = APIRouter(prefix="/alarms", tags=["alarms"])


def _resolve_allowed_macs_for_authorization(authorization: str | None) -> set[str] | None:
    if not authorization:
        return None

    try:
        user = require_session_user(authorization)
    except ValueError:
        return set()

    if user.role in {UserRole.COMMUNITY, UserRole.ADMIN}:
        return None

    if user.role == UserRole.FAMILY:
        family_id = user.family_id or user.id
        directory = get_care_service().get_family_directory(family_id)
        return {
            mac.upper()
            for elder in directory.elders
            for mac in (elder.device_macs or ([elder.device_mac] if elder.device_mac else []))
            if mac
        }

    if user.role == UserRole.ELDER:
        directory = get_care_service().get_directory()
        elder = next((item for item in directory.elders if item.id == user.id), None)
        return {
            mac.upper()
            for mac in ((elder.device_macs if elder else []) or ([elder.device_mac] if elder and elder.device_mac else []))
            if mac
        }

    return None


@router.get("", response_model=list[AlarmRecord])
async def list_alarms(
    device_mac: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    authorization: str | None = Header(default=None),
) -> list[AlarmRecord]:
    alarms = [_enrich_alarm_metadata(alarm) for alarm in get_alarm_service().list_alarms(device_mac=device_mac, active_only=active_only)]
    allowed_macs = _resolve_allowed_macs_for_authorization(authorization)
    if allowed_macs is None:
        return alarms
    return [alarm for alarm in alarms if alarm.device_mac.upper() in allowed_macs]


@router.get("/queue", response_model=list[AlarmQueueItem])
async def list_alarm_queue(
    active_only: bool = Query(default=True),
    authorization: str | None = Header(default=None),
) -> list[AlarmQueueItem]:
    items = [
        AlarmQueueItem(
            score=item.score,
            alarm=_enrich_alarm_metadata(item.alarm),
        )
        for item in get_alarm_service().queue_items(active_only=active_only)
    ]
    allowed_macs = _resolve_allowed_macs_for_authorization(authorization)
    if allowed_macs is None:
        return items
    return [item for item in items if item.alarm.device_mac.upper() in allowed_macs]


@router.get("/queue/snapshot")
async def get_alarm_queue_snapshot() -> dict[str, object]:
    return get_alarm_service().queue_snapshot()


@router.get("/mobile-pushes", response_model=list[MobilePushRecord])
async def list_mobile_pushes(
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> list[MobilePushRecord]:
    pushes = get_alarm_service().list_mobile_pushes(limit=limit)
    allowed_macs = _resolve_allowed_macs_for_authorization(authorization)
    if allowed_macs is None:
        return pushes
    return [record for record in pushes if record.device_mac.upper() in allowed_macs]


@router.post("/{alarm_id}/acknowledge", response_model=AlarmRecord)
async def acknowledge_alarm(alarm_id: str) -> AlarmRecord:
    alarm, collapsed_sibling_ids = get_alarm_service().acknowledge(alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    acked_alarm = _annotate_alarm_timeline(_enrich_alarm_metadata(alarm), ack_ts=datetime.now(timezone.utc))
    repository = get_health_data_repository()
    repository.acknowledge_alert(alarm_id)
    for sibling_id in collapsed_sibling_ids:
        repository.acknowledge_alert(sibling_id)
    await get_websocket_manager().broadcast_alarm(acked_alarm.model_dump(mode="json"))
    await get_websocket_manager().broadcast_alarm_queue(
        {
            "type": "alarm_queue",
            "queue": _serialize_alarm_queue_items(active_only=True),
            "snapshot": get_alarm_service().queue_snapshot(),
        }
    )
    return acked_alarm
