from __future__ import annotations

from backend.models.alarm_model import AlarmQueueItem, AlarmRecord, MobilePushRecord
from backend.models.health_model import HealthSample


class AlarmService:
    """Evaluates incoming samples and stores active alarms."""

    def __init__(self, detector: object, queue: object, notification_service: object) -> None:
        self._detector = detector
        self._queue = queue
        self._notification_service = notification_service
        self._alarms: list[AlarmRecord] = []

    def evaluate(self, sample: HealthSample) -> list[AlarmRecord]:
        alarms = self._detector.evaluate(sample)
        return self.evaluate_alarm_records(alarms)

    def evaluate_alarm_records(self, alarms: list[AlarmRecord]) -> list[AlarmRecord]:
        if alarms:
            self._alarms.extend(alarms)
            for alarm in alarms:
                self._queue.enqueue(alarm)
                self._notification_service.dispatch_mobile_push(alarm)
        self._alarms.sort(key=lambda item: (item.alarm_level.value, item.created_at), reverse=False)
        return alarms

    def list_alarms(self, device_mac: str | None = None, active_only: bool = False) -> list[AlarmRecord]:
        alarms = self._alarms
        if device_mac:
            alarms = [alarm for alarm in alarms if alarm.device_mac == device_mac.upper()]
        if active_only:
            alarms = [alarm for alarm in alarms if not alarm.acknowledged]
        return alarms

    def queue_items(self, active_only: bool = True) -> list[AlarmQueueItem]:
        return self._queue.items(active_only=active_only)

    def queue_snapshot(self) -> dict[str, object]:
        return self._queue.snapshot()

    def list_mobile_pushes(self, limit: int = 50) -> list[MobilePushRecord]:
        return self._notification_service.list_mobile_pushes(limit=limit)

    def acknowledge(self, alarm_id: str) -> AlarmRecord | None:
        for index, alarm in enumerate(self._alarms):
            if alarm.id == alarm_id:
                updated = alarm.model_copy(update={"acknowledged": True})
                self._alarms[index] = updated
                self._queue.remove(alarm_id)
                return updated
        return None
