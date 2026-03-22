from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from backend.models.device_model import DeviceRegisterRequest
from backend.models.user_register_model import ElderRegisterRequest
from backend.services.device_service import DeviceService
from backend.services.user_service import UserService


WORKSPACE_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def build_temp_db_path(name: str) -> Path:
    WORKSPACE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DATA_DIR / f"{name}-{uuid4().hex}.db"


def test_device_registry_and_bind_history_persist_across_service_rebuild() -> None:
    db_path = build_temp_db_path("device-persist")
    try:
        user_service = UserService()
        elder = user_service.register_elder(
            ElderRegisterRequest(
                name="Persist Elder",
                phone="13800990001",
                password="123456",
                age=78,
                apartment="2-301",
            )
        )

        service = DeviceService(user_service=user_service, database_url=sqlite_url(db_path))
        created = service.register_device(
            DeviceRegisterRequest(
                mac_address="53:57:08:01:00:AA",
                device_name="T10-WATCH",
                user_id=elder.id,
            ),
            operator_id="operator-1",
        )

        rebuilt = DeviceService(user_service=user_service, database_url=sqlite_url(db_path))
        loaded = rebuilt.get_device("53:57:08:01:00:AA")

        assert loaded is not None
        assert loaded.id == created.id
        assert loaded.status.value == "offline"
        logs = rebuilt.list_bind_logs("53:57:08:01:00:AA")
        assert len(logs) == 1
        assert logs[0].operator_id == "operator-1"
    finally:
        if db_path.exists():
            db_path.unlink()


def test_delete_device_removes_persisted_registry_and_history() -> None:
    db_path = build_temp_db_path("device-delete")
    try:
        user_service = UserService()
        elder = user_service.register_elder(
            ElderRegisterRequest(
                name="Delete Elder",
                phone="13800990002",
                password="123456",
                age=80,
                apartment="2-302",
            )
        )

        service = DeviceService(user_service=user_service, database_url=sqlite_url(db_path))
        service.register_device(
            DeviceRegisterRequest(
                mac_address="53:57:08:01:00:AB",
                device_name="T10-WATCH",
                user_id=elder.id,
            ),
            operator_id="operator-1",
        )
        deleted = service.delete_device("53:57:08:01:00:AB")
        assert deleted.mac_address == "53:57:08:01:00:AB"

        rebuilt = DeviceService(user_service=user_service, database_url=sqlite_url(db_path))
        assert rebuilt.get_device("53:57:08:01:00:AB") is None
        assert rebuilt.list_bind_logs("53:57:08:01:00:AB") == []
    finally:
        if db_path.exists():
            db_path.unlink()
