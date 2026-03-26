from __future__ import annotations

import asyncio

from backend.api import device_api
from backend.models.auth_model import SessionUser
from backend.models.device_model import (
    DeviceBindStatus,
    DeviceIngestMode,
    DeviceRegisterRequest,
    SerialTargetSwitchRequest,
    ingest_source_matches_mode,
    normalize_and_validate_mac,
)
from backend.models.health_model import IngestionSource
from backend.models.user_model import UserRole
from backend.services.device_service import DeviceService
from backend.services.user_service import UserService


def test_ingest_source_matches_mode() -> None:
    assert ingest_source_matches_mode(DeviceIngestMode.SERIAL, IngestionSource.SERIAL) is True
    assert ingest_source_matches_mode(DeviceIngestMode.MOCK, IngestionSource.MOCK) is True
    assert ingest_source_matches_mode(DeviceIngestMode.SERIAL, IngestionSource.MOCK) is False
    assert ingest_source_matches_mode("serial", "mock") is False


def test_compact_mac_is_normalized_for_registration() -> None:
    assert normalize_and_validate_mac("535708020001") == "53:57:08:02:00:01"
    assert normalize_and_validate_mac("53-57-08-02-00-01") == "53:57:08:02:00:01"
    assert normalize_and_validate_mac("5410260100DF") == "54:10:26:01:00:DF"
    assert normalize_and_validate_mac("54:10:26:01:00:DF") == "54:10:26:01:00:DF"


def test_registering_real_serial_device_detaches_mock_binding(tmp_path) -> None:
    user_service = UserService()
    elder = user_service.seed_elder(
        user_id="user-elder-demo",
        name="李秀英",
        phone="13900009999",
        password="123456",
        age=79,
        apartment="1-102",
    )
    service = DeviceService(
        user_service,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'device-demo.db').as_posix()}",
    )

    mock_device = service.register_device(
        DeviceRegisterRequest(
            mac_address="53:57:08:03:00:01",
            device_name="T10-WATCH",
            user_id=elder.id,
            ingest_mode=DeviceIngestMode.MOCK,
        )
    )
    serial_device = service.register_device(
        DeviceRegisterRequest(
            mac_address="53:57:08:03:00:02",
            device_name="T10-WATCH",
            user_id=elder.id,
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )

    refreshed_mock = service.get_device(mock_device.mac_address)
    refreshed_serial = service.get_device(serial_device.mac_address)

    assert refreshed_mock is not None
    assert refreshed_serial is not None
    assert refreshed_mock.user_id is None
    assert refreshed_mock.bind_status == DeviceBindStatus.UNBOUND
    assert refreshed_serial.user_id == elder.id
    assert refreshed_serial.bind_status == DeviceBindStatus.BOUND
    assert service.get_active_serial_target_mac() == refreshed_serial.mac_address


def test_latest_serial_registration_becomes_active_target_and_falls_back_on_delete(tmp_path) -> None:
    user_service = UserService()
    elder = user_service.seed_elder(
        user_id="user-elder-target",
        name="测试老人",
        phone="13900008888",
        password="123456",
        age=76,
        apartment="2-202",
    )
    service = DeviceService(
        user_service,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'device-target.db').as_posix()}",
    )

    first = service.register_device(
        DeviceRegisterRequest(
            mac_address="53:57:08:04:00:01",
            device_name="T10-WATCH",
            user_id=elder.id,
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )
    second = service.register_device(
        DeviceRegisterRequest(
            mac_address="53:57:08:04:00:02",
            device_name="T10-WATCH",
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )

    assert service.get_active_serial_target_mac() == second.mac_address

    service.delete_device(second.mac_address)

    assert service.get_active_serial_target_mac() == first.mac_address


def test_register_serial_device_without_binding_is_allowed_even_when_elder_has_same_model(tmp_path) -> None:
    user_service = UserService()
    elder = user_service.seed_elder(
        user_id="user-elder-unbound-demo",
        name="空挂演示老人",
        phone="13900007777",
        password="123456",
        age=75,
        apartment="3-301",
    )
    service = DeviceService(
        user_service,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'device-unbound.db').as_posix()}",
    )

    bound = service.register_device(
        DeviceRegisterRequest(
            mac_address="54:10:26:01:00:01",
            device_name="T10-WATCH",
            user_id=elder.id,
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )

    unbound = service.register_device(
        DeviceRegisterRequest(
            mac_address="54:10:26:01:00:02",
            device_name="T10-WATCH",
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )

    assert bound.user_id == elder.id
    assert unbound.user_id is None
    assert unbound.bind_status == DeviceBindStatus.UNBOUND
    assert service.get_active_serial_target_mac() == unbound.mac_address


def test_can_switch_active_serial_target_explicitly(tmp_path) -> None:
    service = DeviceService(
        UserService(),
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'device-switch.db').as_posix()}",
    )

    first = service.register_device(
        DeviceRegisterRequest(
            mac_address="54:10:26:01:00:11",
            device_name="T10-WATCH",
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )
    second = service.register_device(
        DeviceRegisterRequest(
            mac_address="54:10:26:01:00:12",
            device_name="T10-WATCH",
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )

    active, previous = service.set_active_serial_target(first.mac_address)

    assert previous == second.mac_address
    assert active.mac_address == first.mac_address
    assert service.get_active_serial_target_mac() == first.mac_address


def test_switching_mock_device_as_serial_target_is_rejected(tmp_path) -> None:
    service = DeviceService(
        UserService(),
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'device-switch-mock.db').as_posix()}",
    )
    device = service.register_device(
        DeviceRegisterRequest(
            mac_address="53:57:08:03:00:10",
            device_name="T10-WATCH",
            ingest_mode=DeviceIngestMode.MOCK,
        )
    )

    try:
        service.set_active_serial_target(device.mac_address)
    except ValueError as exc:
        assert str(exc) == "DEVICE_NOT_SERIAL"
    else:
        raise AssertionError("expected switching mock device to fail")


def test_serial_target_switch_api_returns_new_target(monkeypatch, tmp_path) -> None:
    service = DeviceService(
        UserService(),
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'device-switch-api.db').as_posix()}",
    )
    first = service.register_device(
        DeviceRegisterRequest(
            mac_address="54:10:26:01:00:21",
            device_name="T10-WATCH",
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )
    second = service.register_device(
        DeviceRegisterRequest(
            mac_address="54:10:26:01:00:22",
            device_name="T10-WATCH",
            ingest_mode=DeviceIngestMode.SERIAL,
        )
    )

    monkeypatch.setattr(device_api, "get_device_service", lambda: service)
    monkeypatch.setattr(
        device_api,
        "require_write_session_user",
        lambda _authorization: SessionUser(
            id="community-demo",
            username="community_demo",
            name="社区演示账号",
            role=UserRole.COMMUNITY,
            community_id="C10001",
        ),
    )

    result = asyncio.run(
        device_api.switch_serial_target(
            SerialTargetSwitchRequest(mac_address=first.mac_address),
            authorization="Bearer demo-token",
        )
    )

    assert result.active_target_mac == first.mac_address
    assert result.previous_target_mac == second.mac_address
    assert result.active_target_device_name == first.device_name
    assert service.get_active_serial_target_mac() == first.mac_address
