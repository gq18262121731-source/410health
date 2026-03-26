from __future__ import annotations

from pathlib import Path

from backend.config import Settings
from backend.runtime_bootstrap import parse_shouhuan_config, resolve_runtime_bootstrap
from backend.runtime_bootstrap import RuntimeBootstrap


def test_parse_shouhuan_config_reads_real_script_constants() -> None:
    config = parse_shouhuan_config(Path("shouhuan.py"))

    assert config.port == "COM3"
    assert config.baudrate == 115200
    assert config.mac_address == "54:10:26:01:00:DF"
    assert config.packet_type == 5


def test_resolve_runtime_bootstrap_enters_serial_mode_when_port_is_available(monkeypatch, tmp_path: Path) -> None:
    script_path = tmp_path / "shouhuan.py"
    script_path.write_text(
        'BAUD_RATE = 115200\nTARGET_COM = "COM7"\nHANDWARE_MAC = "5410260100DF"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.runtime_bootstrap.probe_serial_port",
        lambda port, baudrate: (True, "serial_port_available"),
    )

    runtime = resolve_runtime_bootstrap(script_path)

    assert runtime.mode == "serial"
    assert runtime.bootstrap_source == "shouhuan.py"
    assert runtime.bootstrap_status == "ready"
    assert runtime.bootstrap_reason == "serial_port_available"
    assert runtime.port == "COM7"
    assert runtime.baudrate == 115200
    assert runtime.mac_address == "54:10:26:01:00:DF"


def test_resolve_runtime_bootstrap_falls_back_to_mock_when_port_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    script_path = tmp_path / "shouhuan.py"
    script_path.write_text(
        'BAUD_RATE = 115200\nTARGET_COM = "COM7"\nHANDWARE_MAC = "5410260100DF"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.runtime_bootstrap.probe_serial_port",
        lambda port, baudrate: (False, "serial_open_failed:SerialException"),
    )

    runtime = resolve_runtime_bootstrap(script_path)

    assert runtime.mode == "mock"
    assert runtime.bootstrap_source == "fallback_mock"
    assert runtime.bootstrap_status == "fallback"
    assert runtime.bootstrap_reason == "serial_open_failed:SerialException"
    assert runtime.port == "COM7"
    assert runtime.mac_address == "54:10:26:01:00:DF"


def test_settings_switch_to_serial_when_bootstrap_is_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.config.resolve_runtime_bootstrap",
        lambda script_path: RuntimeBootstrap(
            mode="serial",
            bootstrap_source="shouhuan.py",
            bootstrap_status="ready",
            bootstrap_reason="serial_port_available",
            port="COM3",
            baudrate=115200,
            mac_address="54:10:26:01:00:DF",
            packet_type=5,
        ),
    )

    settings = Settings()

    assert settings.runtime_mode == "serial"
    assert settings.serial_runtime_enabled is True
    assert settings.use_mock_data is False
    assert settings.serial_port == "COM3"
    assert settings.serial_mac_filter == "54:10:26:01:00:DF"


def test_settings_fall_back_to_mock_when_bootstrap_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.config.resolve_runtime_bootstrap",
        lambda script_path: RuntimeBootstrap(
            mode="mock",
            bootstrap_source="fallback_mock",
            bootstrap_status="fallback",
            bootstrap_reason="serial_open_failed:SerialException",
            port="COM3",
            baudrate=115200,
            mac_address="54:10:26:01:00:DF",
            packet_type=5,
        ),
    )

    settings = Settings()

    assert settings.runtime_mode == "mock"
    assert settings.mock_runtime_enabled is True
    assert settings.serial_runtime_enabled is False
    assert settings.use_mock_data is True
    assert settings.serial_port == "COM3"
