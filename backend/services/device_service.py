from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from threading import RLock

from backend.models.device_bind_model import (
    DeviceBindLogRecord,
    DeviceBindRequest,
    DeviceRebindRequest,
    DeviceUnbindRequest,
)
from backend.models.device_model import DeviceBindStatus, DeviceRecord, DeviceRegisterRequest, DeviceStatus
from backend.models.user_model import UserRole
from backend.services.user_service import UserService


class DeviceService:
    """Tracks device registration, ownership and bind history with SQLite persistence."""

    def __init__(self, user_service: UserService | None = None, *, database_url: str | None = None) -> None:
        self._devices: OrderedDict[str, DeviceRecord] = OrderedDict()
        self._bind_logs: list[DeviceBindLogRecord] = []
        self._user_service = user_service
        self._database_path = self._resolve_sqlite_path(database_url)
        self._lock = RLock()
        self._initialize_storage()
        self._load_from_storage()

    def seed_devices(self, devices: list[DeviceRecord]) -> None:
        with self._lock:
            for device in devices:
                if device.mac_address in self._devices:
                    continue
                self._devices[device.mac_address] = device
                self._upsert_device(device)

    def list_devices(self) -> list[DeviceRecord]:
        with self._lock:
            return list(self._devices.values())

    def get_device(self, mac_address: str) -> DeviceRecord | None:
        with self._lock:
            return self._devices.get(mac_address.upper())

    def register_device(self, payload: DeviceRegisterRequest, *, operator_id: str | None = None) -> DeviceRecord:
        with self._lock:
            existing = self.get_device(payload.mac_address)
            if existing:
                raise ValueError("DEVICE_ALREADY_EXISTS")
            device_name = payload.device_name.strip() or "T10-WATCH"
            if payload.user_id:
                self._validate_binding_target(payload.user_id)
                self._ensure_unique_model_per_target_user(payload.user_id, device_name)
                bind_status = DeviceBindStatus.BOUND
                user_id = payload.user_id
            else:
                bind_status = DeviceBindStatus.UNBOUND
                user_id = None
            record = DeviceRecord(
                mac_address=payload.mac_address,
                device_name=device_name,
                user_id=user_id,
                status=DeviceStatus.OFFLINE,
                bind_status=bind_status,
            )
            self._devices[record.mac_address] = record
            self._upsert_device(record)
            if payload.user_id:
                log = DeviceBindLogRecord(
                    device_id=record.id,
                    old_user_id=None,
                    new_user_id=payload.user_id,
                    action_type="bind",
                    operator_id=operator_id,
                )
                self._bind_logs.append(log)
                self._insert_bind_log(log)
            return self._devices[record.mac_address]

    def ensure_device(self, mac_address: str, device_name: str = "T10-WATCH") -> DeviceRecord:
        with self._lock:
            existing = self.get_device(mac_address)
            if existing:
                return existing
            request = DeviceRegisterRequest(mac_address=mac_address, device_name=device_name)
            return self.register_device(request)

    def update_status(self, mac_address: str, status: DeviceStatus) -> DeviceRecord | None:
        with self._lock:
            device = self.get_device(mac_address)
            if not device:
                return None
            updated = device.model_copy(update={"status": status})
            self._devices[mac_address.upper()] = updated
            self._upsert_device(updated)
            return updated

    def bind_device(self, payload: DeviceBindRequest) -> DeviceBindLogRecord:
        with self._lock:
            device = self.get_device(payload.mac_address)
            if device is None:
                raise ValueError("DEVICE_NOT_FOUND")
            self._validate_binding_target(payload.target_user_id)
            if device.user_id and device.user_id != payload.target_user_id:
                raise ValueError("DEVICE_ALREADY_BOUND")
            if device.user_id == payload.target_user_id and device.bind_status == DeviceBindStatus.BOUND:
                raise ValueError("DEVICE_ALREADY_BOUND_TO_TARGET")
            self._ensure_unique_model_per_target_user(
                payload.target_user_id,
                device.device_name,
                current_device_id=device.id,
            )
            updated = device.model_copy(update={"user_id": payload.target_user_id, "bind_status": DeviceBindStatus.BOUND})
            self._devices[updated.mac_address] = updated
            self._upsert_device(updated)
            log = DeviceBindLogRecord(
                device_id=updated.id,
                old_user_id=device.user_id,
                new_user_id=payload.target_user_id,
                action_type="bind",
                operator_id=payload.operator_id,
            )
            self._bind_logs.append(log)
            self._insert_bind_log(log)
            return log

    def unbind_device(self, payload: DeviceUnbindRequest) -> DeviceBindLogRecord:
        with self._lock:
            device = self.get_device(payload.mac_address)
            if device is None:
                raise ValueError("DEVICE_NOT_FOUND")
            if device.user_id is None or device.bind_status != DeviceBindStatus.BOUND:
                raise ValueError("DEVICE_NOT_BOUND")
            updated = device.model_copy(update={"user_id": None, "bind_status": DeviceBindStatus.UNBOUND})
            self._devices[updated.mac_address] = updated
            self._upsert_device(updated)
            log = DeviceBindLogRecord(
                device_id=updated.id,
                old_user_id=device.user_id,
                new_user_id=None,
                action_type="unbind",
                operator_id=payload.operator_id,
                reason=payload.reason,
            )
            self._bind_logs.append(log)
            self._insert_bind_log(log)
            return log

    def rebind_device(self, payload: DeviceRebindRequest) -> DeviceBindLogRecord:
        with self._lock:
            device = self.get_device(payload.mac_address)
            if device is None:
                raise ValueError("DEVICE_NOT_FOUND")
            if device.user_id is None or device.bind_status != DeviceBindStatus.BOUND:
                raise ValueError("DEVICE_NOT_BOUND")
            self._validate_binding_target(payload.new_user_id)
            if device.user_id == payload.new_user_id:
                raise ValueError("DEVICE_ALREADY_BOUND_TO_TARGET")
            self._ensure_unique_model_per_target_user(
                payload.new_user_id,
                device.device_name,
                current_device_id=device.id,
            )
            updated = device.model_copy(update={"user_id": payload.new_user_id, "bind_status": DeviceBindStatus.BOUND})
            self._devices[updated.mac_address] = updated
            self._upsert_device(updated)
            log = DeviceBindLogRecord(
                device_id=updated.id,
                old_user_id=device.user_id,
                new_user_id=payload.new_user_id,
                action_type="rebind",
                operator_id=payload.operator_id,
                reason=payload.reason,
            )
            self._bind_logs.append(log)
            self._insert_bind_log(log)
            return log

    def list_bind_logs(self, mac_address: str | None = None) -> list[DeviceBindLogRecord]:
        with self._lock:
            if mac_address is None:
                return list(self._bind_logs)
            device = self.get_device(mac_address)
            if device is None:
                return []
            return [log for log in self._bind_logs if log.device_id == device.id]

    def delete_device(self, mac_address: str) -> DeviceRecord:
        with self._lock:
            device = self.get_device(mac_address)
            if device is None:
                raise ValueError("DEVICE_NOT_FOUND")
            self._devices.pop(device.mac_address, None)
            self._bind_logs = [log for log in self._bind_logs if log.device_id != device.id]
            self._delete_device(device.id)
            self._delete_bind_logs(device.id)
            return device

    def reset(self) -> None:
        with self._lock:
            self._devices.clear()
            self._bind_logs.clear()
            with self._connection() as connection:
                connection.execute("DELETE FROM device_bind_logs")
                connection.execute("DELETE FROM devices")
                connection.commit()

    def _validate_binding_target(self, user_id: str) -> None:
        if self._user_service is None:
            return
        user = self._user_service.get_user(user_id)
        if user is None:
            raise ValueError("USER_NOT_FOUND")
        if user.role != UserRole.ELDER:
            raise ValueError("INVALID_BIND_TARGET_ROLE")

    def _ensure_unique_model_per_target_user(
        self,
        user_id: str,
        device_name: str,
        *,
        current_device_id: str | None = None,
    ) -> None:
        normalized_name = self._normalize_device_name(device_name)
        for device in self._devices.values():
            if device.user_id != user_id or device.bind_status != DeviceBindStatus.BOUND:
                continue
            if current_device_id and device.id == current_device_id:
                continue
            if self._normalize_device_name(device.device_name) == normalized_name:
                raise ValueError("TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL")

    @staticmethod
    def _normalize_device_name(device_name: str) -> str:
        return device_name.strip().upper()

    def _initialize_storage(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    mac_address TEXT NOT NULL UNIQUE,
                    device_name TEXT NOT NULL,
                    user_id TEXT,
                    status TEXT NOT NULL,
                    bind_status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS device_bind_logs (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    old_user_id TEXT,
                    new_user_id TEXT,
                    action_type TEXT NOT NULL,
                    operator_id TEXT,
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def _load_from_storage(self) -> None:
        with self._lock, self._connection() as connection:
            device_rows = connection.execute(
                """
                SELECT id, mac_address, device_name, user_id, status, bind_status, created_at
                FROM devices
                ORDER BY created_at ASC
                """
            ).fetchall()
            self._devices = OrderedDict(
                (
                    row["mac_address"],
                    DeviceRecord(
                        id=row["id"],
                        mac_address=row["mac_address"],
                        device_name=row["device_name"],
                        user_id=row["user_id"],
                        status=DeviceStatus(row["status"]),
                        bind_status=DeviceBindStatus(row["bind_status"]),
                        created_at=row["created_at"],
                    ),
                )
                for row in device_rows
            )

            bind_rows = connection.execute(
                """
                SELECT id, device_id, old_user_id, new_user_id, action_type, operator_id, reason, created_at
                FROM device_bind_logs
                ORDER BY created_at ASC
                """
            ).fetchall()
            self._bind_logs = [
                DeviceBindLogRecord(
                    id=row["id"],
                    device_id=row["device_id"],
                    old_user_id=row["old_user_id"],
                    new_user_id=row["new_user_id"],
                    action_type=row["action_type"],
                    operator_id=row["operator_id"],
                    reason=row["reason"],
                    created_at=row["created_at"],
                )
                for row in bind_rows
            ]

    def _upsert_device(self, device: DeviceRecord) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO devices (id, mac_address, device_name, user_id, status, bind_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mac_address) DO UPDATE SET
                    id = excluded.id,
                    device_name = excluded.device_name,
                    user_id = excluded.user_id,
                    status = excluded.status,
                    bind_status = excluded.bind_status,
                    created_at = excluded.created_at
                """,
                (
                    device.id,
                    device.mac_address,
                    device.device_name,
                    device.user_id,
                    device.status.value,
                    device.bind_status.value,
                    device.created_at.isoformat(),
                ),
            )
            connection.commit()

    def _insert_bind_log(self, log: DeviceBindLogRecord) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO device_bind_logs
                (id, device_id, old_user_id, new_user_id, action_type, operator_id, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.id,
                    log.device_id,
                    log.old_user_id,
                    log.new_user_id,
                    log.action_type,
                    log.operator_id,
                    log.reason,
                    log.created_at.isoformat(),
                ),
            )
            connection.commit()

    def _delete_device(self, device_id: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM devices WHERE id = ?", (device_id,))
            connection.commit()

    def _delete_bind_logs(self, device_id: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM device_bind_logs WHERE device_id = ?", (device_id,))
            connection.commit()

    @contextmanager
    def _connection(self):
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _resolve_sqlite_path(database_url: str | None) -> Path:
        if not database_url:
            return Path("data") / "app.db"
        prefix = "sqlite+aiosqlite:///"
        if database_url.startswith(prefix):
            return Path(database_url[len(prefix):])
        return Path("data") / "app.db"
