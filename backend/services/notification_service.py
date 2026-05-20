from __future__ import annotations

from backend.models.alarm_model import AlarmPriority, AlarmRecord, MobilePushRecord
from backend.models.notification_model import (
    MobilePushDeviceRecord,
    MobilePushDeviceUpsertRequest,
    MobilePushDispatchRecord,
    MobilePushDispatchTarget,
)
from backend.models.auth_model import SessionUser
from backend.repositories.mobile_push_device_repo import MobilePushDeviceRepository


class NotificationService:
    """Tracks mobile push intent records and prepares remote-push-ready dispatch targets."""

    def __init__(self, device_repo: MobilePushDeviceRepository) -> None:
        self._device_repo = device_repo
        self._push_records: list[MobilePushRecord] = []
        self._dispatch_records: list[MobilePushDispatchRecord] = []

    def register_mobile_device(
        self,
        *,
        user: SessionUser,
        payload: MobilePushDeviceUpsertRequest,
    ) -> MobilePushDeviceRecord:
        return self._device_repo.upsert_for_user(user=user, payload=payload)

    def list_mobile_devices_for_user(self, user_id: str) -> list[MobilePushDeviceRecord]:
        return self._device_repo.list_active_for_user(user_id)

    def revoke_mobile_device(self, *, user_id: str, installation_id: str) -> MobilePushDeviceRecord | None:
        return self._device_repo.revoke_for_user_installation(user_id=user_id, installation_id=installation_id)

    def dispatch_mobile_push(self, alarm: AlarmRecord) -> MobilePushRecord:
        targets = self._resolve_dispatch_targets(alarm)
        dispatch_record = MobilePushDispatchRecord(
            alarm_id=alarm.id,
            device_mac=alarm.device_mac,
            recipient_count=len(targets),
            remote_ready_count=sum(1 for target in targets if target.remote_push_ready),
            targets=targets,
        )
        self._dispatch_records.append(dispatch_record)

        record = MobilePushRecord(
            alarm_id=alarm.id,
            device_mac=alarm.device_mac,
            title=self._title_for(alarm.alarm_level),
            body=alarm.message,
            priority=alarm.alarm_level,
            recipient_count=dispatch_record.recipient_count,
            remote_ready_count=dispatch_record.remote_ready_count,
            metadata={
                "alarm_type": alarm.alarm_type.value,
                "dispatch_target_installations": [target.installation_id for target in targets],
                "dispatch_target_user_ids": [target.user_id for target in targets],
            },
        )
        self._push_records.append(record)
        return record

    def list_mobile_pushes(self, limit: int = 50) -> list[MobilePushRecord]:
        return list(reversed(self._push_records[-limit:]))

    def list_dispatch_records(self, limit: int = 50) -> list[MobilePushDispatchRecord]:
        return list(reversed(self._dispatch_records[-limit:]))

    def _resolve_dispatch_targets(self, alarm: AlarmRecord) -> list[MobilePushDispatchTarget]:
        recipient_user_ids = self._resolve_recipient_user_ids(alarm)
        if not recipient_user_ids:
            return []

        devices = self._device_repo.list_active_for_users(recipient_user_ids)
        targets: list[MobilePushDispatchTarget] = []
        for device in devices:
            targets.append(
                MobilePushDispatchTarget(
                    installation_id=device.installation_id,
                    user_id=device.user_id,
                    provider=device.provider,
                    platform=device.platform,
                    notifications_enabled=device.notifications_enabled,
                    remote_push_ready=device.remote_push_ready,
                )
            )
        return targets

    @staticmethod
    def _resolve_recipient_user_ids(alarm: AlarmRecord) -> list[str]:
        metadata = alarm.metadata or {}
        family_ids = [str(value).strip() for value in metadata.get("family_ids", []) if str(value).strip()]
        if family_ids:
            return family_ids
        elder_id = str(metadata.get("elder_id", "")).strip()
        return [elder_id] if elder_id else []

    @staticmethod
    def _title_for(priority: AlarmPriority) -> str:
        if priority == AlarmPriority.SOS:
            return "SOS 紧急告警"
        if priority == AlarmPriority.CRITICAL:
            return "生命体征危急"
        if priority == AlarmPriority.WARNING:
            return "健康预警通知"
        return "健康通知"
