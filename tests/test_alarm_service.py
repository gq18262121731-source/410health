from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.models.alarm_model import AlarmLayer, AlarmPriority, AlarmRecord, AlarmType
from backend.services.alarm_priority_queue import AlarmPriorityQueue
from backend.services.alarm_service import AlarmService


class _NotificationStub:
    def __init__(self) -> None:
        self.records: list[AlarmRecord] = []

    def dispatch_mobile_push(self, alarm: AlarmRecord) -> None:
        self.records.append(alarm)


class _DetectorStub:
    def evaluate(self, sample) -> list[AlarmRecord]:
        return []


def _build_sos_alarm(*, created_at: datetime, acknowledged: bool = False) -> AlarmRecord:
    return AlarmRecord(
        device_mac="54:10:26:01:00:DF",
        alarm_type=AlarmType.SOS,
        alarm_level=AlarmPriority.SOS,
        alarm_layer=AlarmLayer.REALTIME,
        message="SOS",
        created_at=created_at,
        acknowledged=acknowledged,
        metadata={"event": "sos_broadcast", "is_real_device": True},
    )


def test_alarm_service_dedupes_active_sos_alarm() -> None:
    notification = _NotificationStub()
    service = AlarmService(
        detector=_DetectorStub(),
        queue=AlarmPriorityQueue(redis_url="redis://localhost:6379/0"),
        notification_service=notification,
        sos_dedupe_window_seconds=15,
    )
    first = _build_sos_alarm(created_at=datetime(2026, 3, 25, 1, 0, tzinfo=timezone.utc))
    second = _build_sos_alarm(created_at=first.created_at + timedelta(seconds=8))

    emitted_first = service.evaluate_alarm_records([first])
    emitted_second = service.evaluate_alarm_records([second])

    assert len(service.list_alarms(active_only=True)) == 1
    assert emitted_first[0].id == emitted_second[0].id
    assert len(notification.records) == 1


def test_alarm_service_creates_new_sos_after_acknowledge() -> None:
    notification = _NotificationStub()
    service = AlarmService(
        detector=_DetectorStub(),
        queue=AlarmPriorityQueue(redis_url="redis://localhost:6379/0"),
        notification_service=notification,
        sos_dedupe_window_seconds=15,
    )
    first = _build_sos_alarm(created_at=datetime(2026, 3, 25, 1, 0, tzinfo=timezone.utc))
    created = service.evaluate_alarm_records([first])[0]
    service.acknowledge(created.id)

    second = _build_sos_alarm(created_at=first.created_at + timedelta(seconds=20))
    emitted = service.evaluate_alarm_records([second])[0]

    assert emitted.id != created.id
    assert len(service.list_alarms(active_only=True)) == 1
