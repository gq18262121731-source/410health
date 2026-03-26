from __future__ import annotations

from datetime import timedelta

from backend.models.alarm_model import AlarmQueueItem, AlarmRecord, MobilePushRecord
from backend.models.health_model import HealthSample


class AlarmService:
    """Evaluates incoming samples and stores active alarms."""

    def __init__(
        self,
        detector: object,
        queue: object,
        notification_service: object,
        *,
        sos_dedupe_window_seconds: int = 15,
    ) -> None:
        self._detector = detector
        self._queue = queue
        self._notification_service = notification_service
        self._alarms: list[AlarmRecord] = []
        self._sos_dedupe_window = timedelta(seconds=max(1, sos_dedupe_window_seconds))

    def evaluate(self, sample: HealthSample) -> list[AlarmRecord]:
        alarms = self._detector.evaluate(sample)
        return self.evaluate_alarm_records(alarms)

    def evaluate_alarm_records(self, alarms: list[AlarmRecord]) -> list[AlarmRecord]:
        normalized: list[AlarmRecord] = []
        if alarms:
            for alarm in alarms:
                normalized.append(self._upsert_alarm(alarm))
        self._alarms.sort(key=lambda item: (item.alarm_level.value, item.created_at), reverse=False)
        return normalized

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

    def _upsert_alarm(self, alarm: AlarmRecord) -> AlarmRecord:
        existing_index = self._find_active_sos_index(alarm)
        if existing_index is not None:
            existing = self._alarms[existing_index]
            updated = existing.model_copy(
                update={
                    "created_at": alarm.created_at,
                    "message": alarm.message,
                    "anomaly_probability": alarm.anomaly_probability,
                    "alarm_level": alarm.alarm_level,
                    "alarm_layer": alarm.alarm_layer,
                    "metadata": {**existing.metadata, **alarm.metadata},
                }
            )
            self._alarms[existing_index] = updated
            self._queue.remove(existing.id)
            self._queue.enqueue(updated)
            return updated

        self._alarms.append(alarm)
        self._queue.enqueue(alarm)
        self._notification_service.dispatch_mobile_push(alarm)
        return alarm

    def _find_active_sos_index(self, alarm: AlarmRecord) -> int | None:
        if alarm.alarm_type.value != "sos":
            return None
        for index in range(len(self._alarms) - 1, -1, -1):
            existing = self._alarms[index]
            if existing.alarm_type.value != "sos":
                continue
            if existing.device_mac != alarm.device_mac or existing.acknowledged:
                continue
            # Only dedupe within a short SOS window; outside window create a new alarm id
            # so community/family clients can receive a fresh alert event.
            if alarm.created_at - existing.created_at <= self._sos_dedupe_window:
                return index
            return None
        return None
