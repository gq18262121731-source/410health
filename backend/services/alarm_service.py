from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.models.alarm_model import AlarmQueueItem, AlarmRecord, MobilePushRecord
from backend.models.health_model import HealthSample


logger = logging.getLogger(__name__)


class AlarmService:
    """Evaluates incoming samples and stores active alarms."""

    def __init__(
        self,
        detector: object,
        queue: object,
        notification_service: object,
        *,
        sos_dedupe_window_seconds: int = 15,
        sos_release_window_seconds: int = 2,
    ) -> None:
        self._detector = detector
        self._queue = queue
        self._notification_service = notification_service
        self._alarms: list[AlarmRecord] = []
        self._sos_dedupe_window = timedelta(seconds=max(1, sos_dedupe_window_seconds))
        self._sos_release_window = timedelta(seconds=max(1, sos_release_window_seconds))
        # Post-acknowledgment cooldown: after a user dismisses an SOS popup,
        # some bracelet firmware may continue broadcasting SOS bits for a while.
        # This dict tracks {device_mac: ack_timestamp} so we can suppress
        # repeated alerts from the same physical event.
        self._sos_ack_cooldowns: dict[str, datetime] = {}
        self._fall_ack_cooldowns: dict[str, datetime] = {}
        self._last_non_sos_sample_at: dict[str, datetime] = {}
        # Keep post-ack suppression short; long cooldowns can hide true new SOS events.
        # Use a small multiple of the dedupe window to absorb lingering packets only.
        self._sos_ack_cooldown_duration = timedelta(
            seconds=max(20, int(self._sos_dedupe_window.total_seconds() * 2)),
        )
        self._fall_ack_cooldown_duration = timedelta(seconds=60)

    def evaluate(self, sample: HealthSample) -> list[AlarmRecord]:
        alarms = self._detector.evaluate(sample)
        return self.evaluate_alarm_records(alarms)

    def evaluate_alarm_records(self, alarms: list[AlarmRecord]) -> list[AlarmRecord]:
        normalized: list[AlarmRecord] = []
        if alarms:
            for alarm in alarms:
                upserted = self._upsert_alarm(alarm)
                if upserted is not None:
                    normalized.append(upserted)
        self._alarms.sort(key=lambda item: (item.alarm_level.value, item.created_at), reverse=False)
        return normalized

    def list_alarms(self, device_mac: str | None = None, active_only: bool = False) -> list[AlarmRecord]:
        alarms = self._alarms
        if device_mac:
            normalized_mac = self._normalize_mac(device_mac)
            alarms = [alarm for alarm in alarms if self._normalize_mac(alarm.device_mac) == normalized_mac]
        if active_only:
            alarms = [alarm for alarm in alarms if not alarm.acknowledged]
        return alarms

    def queue_items(self, active_only: bool = True) -> list[AlarmQueueItem]:
        return self._queue.items(active_only=active_only)

    def queue_snapshot(self) -> dict[str, object]:
        return self._queue.snapshot()

    def list_mobile_pushes(self, limit: int = 50) -> list[MobilePushRecord]:
        return self._notification_service.list_mobile_pushes(limit=limit)

    @staticmethod
    def _normalize_mac(device_mac: str) -> str:
        compact = "".join(ch for ch in device_mac if ch.isalnum()).upper()
        if len(compact) == 12:
            return ":".join(compact[i : i + 2] for i in range(0, 12, 2))
        return device_mac.upper()

    def clear_device_sos_state(self, device_mac: str) -> list[str]:
        """Clear transient SOS suppression state for a specific device.

        This is used when a device is (re)bound so the next SOS from the same
        physical band is treated as a fresh event for the new owner context.
        Returns the IDs of active SOS alarms that were collapsed.
        """
        normalized_mac = self._normalize_mac(device_mac)
        self._sos_ack_cooldowns.pop(normalized_mac, None)
        self._last_non_sos_sample_at.pop(normalized_mac, None)
        cleared_alarm_ids: list[str] = []
        for index, existing in enumerate(self._alarms):
            if existing.alarm_type.value != "sos" or existing.acknowledged:
                continue
            if self._normalize_mac(existing.device_mac) != normalized_mac:
                continue
            self._alarms[index] = existing.model_copy(update={"acknowledged": True})
            self._queue.remove(existing.id)
            cleared_alarm_ids.append(existing.id)
        if cleared_alarm_ids:
            logger.info(
                "Cleared %d residual SOS alarms for %s after device binding context changed.",
                len(cleared_alarm_ids),
                normalized_mac,
            )
        return cleared_alarm_ids

    def observe_sample(self, sample: HealthSample) -> list[str]:
        normalized_mac = self._normalize_mac(sample.device_mac)
        if sample.sos_flag:
            return []

        self._last_non_sos_sample_at[normalized_mac] = sample.timestamp
        return []

    def acknowledge(self, alarm_id: str) -> tuple[AlarmRecord | None, list[str]]:
        for index, alarm in enumerate(self._alarms):
            if alarm.id == alarm_id:
                updated = alarm.model_copy(update={"acknowledged": True})
                self._alarms[index] = updated
                self._queue.remove(alarm_id)
                collapsed_sibling_ids: list[str] = []
                # Record SOS acknowledgment so subsequent broadcasts from
                # the same physical button press are silently suppressed.
                if alarm.alarm_type.value == "sos":
                    mac = self._normalize_mac(alarm.device_mac)
                    self._sos_ack_cooldowns[mac] = datetime.now(timezone.utc)
                    collapsed_sibling_ids = self._acknowledge_active_sos_siblings(
                        device_mac=mac,
                        exclude_alarm_id=alarm_id,
                    )
                    logger.info(
                        "SOS acknowledged for %s (collapsed %d sibling alarms) - cooldown active for %ds.",
                        mac,
                        len(collapsed_sibling_ids),
                        self._sos_ack_cooldown_duration.total_seconds(),
                    )
                elif alarm.alarm_type.value in {"fall_detected", "fall_injury_risk"}:
                    identity = self._fall_alarm_identity(alarm)
                    self._fall_ack_cooldowns[identity] = datetime.now(timezone.utc)
                return updated, collapsed_sibling_ids
        return None, []

    def acknowledge_many(self, alarm_ids: set[str]) -> list[AlarmRecord]:
        acknowledged: list[AlarmRecord] = []
        if not alarm_ids:
            return acknowledged

        for index, alarm in enumerate(self._alarms):
            if alarm.id not in alarm_ids or alarm.acknowledged:
                continue
            updated = alarm.model_copy(update={"acknowledged": True})
            self._alarms[index] = updated
            self._queue.remove(alarm.id)
            if alarm.alarm_type.value in {"fall_detected", "fall_injury_risk"}:
                identity = self._fall_alarm_identity(alarm)
                self._fall_ack_cooldowns[identity] = datetime.now(timezone.utc)
            acknowledged.append(updated)

        return acknowledged

    def _acknowledge_active_sos_siblings(self, *, device_mac: str, exclude_alarm_id: str) -> list[str]:
        acknowledged_ids: list[str] = []
        normalized_mac = self._normalize_mac(device_mac)
        for index, existing in enumerate(self._alarms):
            if existing.id == exclude_alarm_id:
                continue
            if existing.alarm_type.value != "sos":
                continue
            if existing.acknowledged:
                continue
            if self._normalize_mac(existing.device_mac) != normalized_mac:
                continue
            self._alarms[index] = existing.model_copy(update={"acknowledged": True})
            self._queue.remove(existing.id)
            acknowledged_ids.append(existing.id)
        return acknowledged_ids

    def _upsert_alarm(self, alarm: AlarmRecord) -> AlarmRecord | None:
        # Check post-acknowledgment cooldown first: if the user just dismissed
        # an SOS for this device, suppress subsequent SOS packets silently.
        if alarm.alarm_type.value == "sos" and self._is_in_sos_ack_cooldown(alarm.device_mac):
            return None
        if alarm.alarm_type.value in {"fall_detected", "fall_injury_risk"}:
            if self._is_in_fall_ack_cooldown(alarm):
                logger.info("Fall alarm suppressed by ack cooldown for %s", self._fall_alarm_identity(alarm))
                return None
            existing_fall_index = self._find_active_fall_index(alarm)
            if existing_fall_index is not None:
                existing_fall = self._alarms[existing_fall_index]
                if not self._should_refresh_fall_alarm(existing_fall, alarm):
                    logger.info(
                        "Fall alarm not refreshed for %s: existing=%s incoming=%s",
                        self._fall_alarm_identity(alarm),
                        self._fall_alarm_signature(existing_fall),
                        self._fall_alarm_signature(alarm),
                    )
                    return None
                refreshed_alarm = self._merge_fall_alarm_refresh(existing_fall, alarm)
                self._queue.remove(existing_fall.id)
                self._alarms[existing_fall_index] = refreshed_alarm
                self._queue.enqueue(refreshed_alarm)
                self._notification_service.dispatch_mobile_push(refreshed_alarm)
                logger.info(
                    "Fall alarm refreshed for %s: type=%s level=%s",
                    self._fall_alarm_identity(refreshed_alarm),
                    refreshed_alarm.alarm_type.value,
                    refreshed_alarm.alarm_level.value,
                )
                return refreshed_alarm

        existing_index = self._find_active_sos_index(alarm)
        if existing_index is not None:
            self._collapse_active_sos_duplicates(
                device_mac=alarm.device_mac,
                keep_alarm_id=self._alarms[existing_index].id,
            )
            # Repeated SOS packets from the same active event should not emit
            # another queue item or trigger another popup on clients.
            return None

        self._alarms.append(alarm)
        self._queue.enqueue(alarm)
        self._notification_service.dispatch_mobile_push(alarm)
        if alarm.alarm_type.value in {"fall_detected", "fall_injury_risk"}:
            logger.info(
                "Fall alarm enqueued for %s: type=%s level=%s",
                self._fall_alarm_identity(alarm),
                alarm.alarm_type.value,
                alarm.alarm_level.value,
            )
        return alarm

    def _is_in_sos_ack_cooldown(self, device_mac: str) -> bool:
        """Return True if the device is within the post-acknowledgment cooldown."""
        mac = self._normalize_mac(device_mac)
        ack_at = self._sos_ack_cooldowns.get(mac)
        if ack_at is None:
            return False
        elapsed = datetime.now(timezone.utc) - ack_at
        if elapsed > self._sos_ack_cooldown_duration:
            # Cooldown expired - clear it so future SOS events are not affected.
            del self._sos_ack_cooldowns[mac]
            return False
        logger.debug(
            "SOS suppressed for %s - within post-ack cooldown (%ds/%ds elapsed).",
            mac,
            elapsed.total_seconds(),
            self._sos_ack_cooldown_duration.total_seconds(),
        )
        return True

    def _is_in_fall_ack_cooldown(self, alarm: AlarmRecord) -> bool:
        identity = self._fall_alarm_identity(alarm)
        ack_at = self._fall_ack_cooldowns.get(identity)
        if ack_at is None:
            return False
        elapsed = datetime.now(timezone.utc) - ack_at
        if elapsed > self._fall_ack_cooldown_duration:
            del self._fall_ack_cooldowns[identity]
            return False
        logger.debug(
            "Fall alarm suppressed for %s - within post-ack cooldown (%ds/%ds elapsed).",
            identity,
            elapsed.total_seconds(),
            self._fall_ack_cooldown_duration.total_seconds(),
        )
        return True

    def _find_active_fall_index(self, alarm: AlarmRecord) -> int | None:
        identity = self._fall_alarm_identity(alarm)
        for index in range(len(self._alarms) - 1, -1, -1):
            existing = self._alarms[index]
            if existing.acknowledged:
                continue
            if existing.alarm_type.value not in {"fall_detected", "fall_injury_risk"}:
                continue
            if self._fall_alarm_identity(existing) == identity:
                return index
        return None

    @staticmethod
    def _fall_alarm_signature(alarm: AlarmRecord) -> tuple[str, str, str]:
        metadata = alarm.metadata or {}
        event = metadata.get("event") if isinstance(metadata.get("event"), dict) else {}
        state = str(event.get("state") or "")
        severity = str(event.get("severity") or metadata.get("severity") or "")
        injury_level = str(
            (event.get("injury") or {}).get("level") if isinstance(event.get("injury"), dict) else metadata.get("injury_level") or ""
        )
        return state, severity, injury_level

    @staticmethod
    def _fall_alarm_identity(alarm: AlarmRecord) -> str:
        metadata = alarm.metadata or {}
        event = metadata.get("event") if isinstance(metadata.get("event"), dict) else {}
        incident_id = str(
            metadata.get("incident_id")
            or (event.get("incident_id") if isinstance(event, dict) else "")
            or ""
        ).strip()
        if incident_id:
            return incident_id

        track_id = str(
            metadata.get("track_id")
            or (event.get("track_id") if isinstance(event, dict) else "")
            or ""
        ).strip()
        if track_id:
            return f"{alarm.device_mac.upper()}|{track_id}"
        return f"{alarm.device_mac.upper()}|{alarm.alarm_type.value}|{alarm.created_at.isoformat()}"

    def _should_refresh_fall_alarm(self, existing: AlarmRecord, incoming: AlarmRecord) -> bool:
        if incoming.alarm_level.value < existing.alarm_level.value:
            return True
        if self._fall_alarm_signature(existing) != self._fall_alarm_signature(incoming):
            return True
        existing_score = float(existing.anomaly_probability or 0.0)
        incoming_score = float(incoming.anomaly_probability or 0.0)
        if incoming_score >= existing_score + 0.08:
            return True
        elapsed = incoming.created_at - existing.created_at
        return elapsed >= timedelta(seconds=30)

    @staticmethod
    def _fall_alarm_event(alarm: AlarmRecord) -> dict[str, object]:
        metadata = alarm.metadata or {}
        event = metadata.get("event")
        return dict(event) if isinstance(event, dict) else {}

    @staticmethod
    def _fall_alarm_state_rank(state: str) -> int:
        normalized = (state or "").strip().lower()
        if normalized in {"emergency", "needs_assistance"}:
            return 6
        if normalized in {"abnormal_recovery", "confirmed_fall"}:
            return 5
        if normalized in {"post_fall_monitoring", "injury_watch", "recovery_watch"}:
            return 4
        if normalized in {"suspected_fall", "possible_fall"}:
            return 3
        if normalized:
            return 2
        return 0

    @classmethod
    def _merge_fall_alarm_refresh(cls, existing: AlarmRecord, incoming: AlarmRecord) -> AlarmRecord:
        existing_metadata = dict(existing.metadata or {})
        incoming_metadata = dict(incoming.metadata or {})
        merged_metadata = dict(existing_metadata)
        merged_metadata.update(incoming_metadata)

        existing_event = cls._fall_alarm_event(existing)
        incoming_event = cls._fall_alarm_event(incoming)
        merged_event = dict(existing_event)
        merged_event.update(incoming_event)

        # Preserve the richer confirmed-fall evidence when a later status update
        # for the same incident arrives without a new snapshot.
        existing_snapshot = existing_event.get("snapshot_path")
        incoming_snapshot = incoming_event.get("snapshot_path")
        if isinstance(existing_snapshot, str) and existing_snapshot.strip():
            if not (isinstance(incoming_snapshot, str) and incoming_snapshot.strip()):
                merged_event["snapshot_path"] = existing_snapshot

        existing_state = str(existing_event.get("state") or "")
        incoming_state = str(incoming_event.get("state") or "")
        if cls._fall_alarm_state_rank(existing_state) > cls._fall_alarm_state_rank(incoming_state):
            merged_event["state"] = existing_state
            existing_event_type = existing_event.get("event_type")
            if isinstance(existing_event_type, str) and existing_event_type.strip():
                merged_event["event_type"] = existing_event_type
            existing_severity = existing_event.get("severity")
            if isinstance(existing_severity, str) and existing_severity.strip():
                merged_event["severity"] = existing_severity
            existing_injury = existing_event.get("injury")
            if isinstance(existing_injury, dict) and existing_injury:
                merged_event["injury"] = dict(existing_injury)

        merged_metadata["event"] = merged_event
        for key in ("incident_id", "track_id", "severity", "injury_level"):
            incoming_value = incoming_metadata.get(key)
            if incoming_value in (None, "") and existing_metadata.get(key) not in (None, ""):
                merged_metadata[key] = existing_metadata[key]

        merged_alarm_level = existing.alarm_level
        if incoming.alarm_level.value < existing.alarm_level.value:
            merged_alarm_level = incoming.alarm_level
        merged_probability = max(float(existing.anomaly_probability or 0.0), float(incoming.anomaly_probability or 0.0))
        merged_message = incoming.message
        if cls._fall_alarm_state_rank(existing_state) > cls._fall_alarm_state_rank(incoming_state):
            merged_message = existing.message

        return incoming.model_copy(
            update={
                "metadata": merged_metadata,
                "alarm_level": merged_alarm_level,
                "anomaly_probability": merged_probability,
                "message": merged_message,
            }
        )

    def _find_active_sos_index(self, alarm: AlarmRecord) -> int | None:
        if alarm.alarm_type.value != "sos":
            return None
        incoming_mac = self._normalize_mac(alarm.device_mac)
        last_non_sos_at = self._last_non_sos_sample_at.get(incoming_mac)
        for index in range(len(self._alarms) - 1, -1, -1):
            existing = self._alarms[index]
            if existing.alarm_type.value != "sos":
                continue
            if self._normalize_mac(existing.device_mac) != incoming_mac or existing.acknowledged:
                continue
            if (
                last_non_sos_at is not None
                and last_non_sos_at >= existing.created_at + self._sos_release_window
            ):
                # A new non-SOS sample means the previous SOS packet burst has
                # ended. Treat subsequent SOS as a new event, but do not
                # auto-acknowledge existing alarms; only users should clear them.
                continue
            # A single SOS button press causes multiple broadcast packets.
            # Group unacknowledged packets within the configured dedupe window.
            # If an unacknowledged alarm is older than that window, treat it as
            # stale and clear it so a fresh SOS can trigger a new popup.
            age = alarm.created_at - existing.created_at
            if age > self._sos_dedupe_window:
                self._alarms[index] = existing.model_copy(update={"acknowledged": True})
                self._queue.remove(existing.id)
                continue
            return index
        return None

    def _collapse_active_sos_duplicates(self, *, device_mac: str, keep_alarm_id: str) -> None:
        normalized_mac = self._normalize_mac(device_mac)
        for index, existing in enumerate(self._alarms):
            if existing.id == keep_alarm_id:
                continue
            if existing.alarm_type.value != "sos":
                continue
            if self._normalize_mac(existing.device_mac) != normalized_mac or existing.acknowledged:
                continue
            self._alarms[index] = existing.model_copy(update={"acknowledged": True})
            self._queue.remove(existing.id)
