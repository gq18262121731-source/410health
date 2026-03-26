from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import backend.dependencies as dependencies
from backend.models.device_model import DeviceIngestMode, DeviceRecord
from backend.models.health_model import HealthSample, IngestionSource


def test_display_ready_sample_rejects_incomplete_serial_payload() -> None:
    sample = HealthSample(
        device_mac="54:10:26:01:00:DF",
        timestamp=datetime.now(timezone.utc),
        heart_rate=0,
        temperature=30.0,
        blood_oxygen=0,
        blood_pressure="0/0",
        battery=0,
        source=IngestionSource.SERIAL,
        packet_type="response_a",
    )

    assert dependencies.is_display_ready_sample(sample, DeviceIngestMode.SERIAL) is False


def test_display_ready_sample_treats_known_demo_mac_as_mock_even_if_stored_mode_is_serial(monkeypatch) -> None:
    monkeypatch.setattr(
        dependencies,
        "_data_generator",
        SimpleNamespace(personas=[SimpleNamespace(mac_address="53:57:08:00:00:01")]),
    )
    sample = HealthSample(
        device_mac="53:57:08:00:00:01",
        timestamp=datetime.now(timezone.utc),
        heart_rate=78,
        temperature=36.7,
        blood_oxygen=98,
        blood_pressure="119/78",
        battery=86,
        source=IngestionSource.MOCK,
    )

    assert dependencies.is_display_ready_sample(sample, DeviceIngestMode.SERIAL) is True
    assert dependencies.get_effective_device_ingest_mode("53:57:08:00:00:01", DeviceIngestMode.SERIAL) == DeviceIngestMode.MOCK


def test_display_latest_sample_falls_back_to_persisted_real_sample_when_stream_is_empty(monkeypatch) -> None:
    persisted_sample = HealthSample(
        device_mac="54:10:26:01:00:DF",
        timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        heart_rate=74,
        temperature=36.6,
        blood_oxygen=98,
        blood_pressure="121/79",
        battery=88,
        source=IngestionSource.SERIAL,
        packet_type="response_ab",
    )
    published: list[HealthSample] = []

    monkeypatch.setattr(dependencies, "_stream_service", SimpleNamespace(recent=lambda mac, limit=240: [], publish=published.append))
    monkeypatch.setattr(
        dependencies,
        "_health_data_repository",
        SimpleNamespace(
            list_samples=lambda **kwargs: [persisted_sample],
        ),
    )

    sample = dependencies.get_display_latest_sample("54:10:26:01:00:DF", DeviceIngestMode.SERIAL)

    assert sample == persisted_sample
    assert published == [persisted_sample]


def test_restore_recent_samples_to_stream_publishes_only_display_ready_samples(monkeypatch) -> None:
    valid_serial = HealthSample(
        device_mac="54:10:26:01:00:DF",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
        heart_rate=72,
        temperature=36.5,
        blood_oxygen=97,
        blood_pressure="120/80",
        battery=91,
        source=IngestionSource.SERIAL,
        packet_type="response_ab",
    )
    invalid_serial = HealthSample(
        device_mac="54:10:26:01:00:DF",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=10),
        heart_rate=0,
        temperature=30.0,
        blood_oxygen=0,
        blood_pressure="0/0",
        battery=0,
        source=IngestionSource.SERIAL,
        packet_type="response_a",
    )
    mock_sample = HealthSample(
        device_mac="53:57:08:00:00:01",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=3),
        heart_rate=78,
        temperature=36.7,
        blood_oxygen=98,
        blood_pressure="119/78",
        battery=86,
        source=IngestionSource.MOCK,
    )
    published: list[HealthSample] = []
    devices = [
        DeviceRecord(mac_address="54:10:26:01:00:DF", ingest_mode=DeviceIngestMode.SERIAL),
        DeviceRecord(mac_address="53:57:08:00:00:01", ingest_mode=DeviceIngestMode.MOCK),
    ]

    monkeypatch.setattr(dependencies, "_device_service", SimpleNamespace(list_devices=lambda: devices))
    monkeypatch.setattr(
        dependencies,
        "_health_data_repository",
        SimpleNamespace(
            list_samples_by_devices=lambda **kwargs: {
                "54:10:26:01:00:DF": [invalid_serial, valid_serial],
                "53:57:08:00:00:01": [mock_sample],
            }
        ),
    )
    monkeypatch.setattr(dependencies, "_stream_service", SimpleNamespace(publish=published.append))

    dependencies._restore_recent_samples_to_stream(hours=24, per_device_limit=12)

    assert published == [valid_serial, mock_sample]


def test_display_sample_resolution_carries_forward_latest_valid_serial_fields() -> None:
    latest_valid = HealthSample(
        device_mac="54:10:26:01:00:DF",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=2),
        heart_rate=70,
        temperature=35.01,
        blood_oxygen=98,
        blood_pressure="109/68",
        battery=78,
        steps=350,
        source=IngestionSource.SERIAL,
        packet_type="response_ab",
    )
    noisy_latest = latest_valid.model_copy(
        update={
            "timestamp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "heart_rate": 66,
            "temperature": 28.2,
            "blood_oxygen": 0,
            "blood_pressure": "104/74",
            "steps": 686,
            "packet_type": "response_ab",
        }
    )

    resolved = dependencies._filter_display_samples(
        [latest_valid, noisy_latest],
        DeviceIngestMode.SERIAL,
    )

    assert len(resolved) == 2
    assert resolved[-1].timestamp == noisy_latest.timestamp
    assert resolved[-1].heart_rate == 66
    assert resolved[-1].blood_pressure == "104/74"
    assert resolved[-1].steps == 686
    assert resolved[-1].blood_oxygen == 98
    assert resolved[-1].temperature == 28.2


def test_display_ready_sample_accepts_raw_serial_temperature_below_30() -> None:
    sample = HealthSample(
        device_mac="54:10:26:01:00:DF",
        timestamp=datetime.now(timezone.utc),
        heart_rate=74,
        temperature=29.17,
        blood_oxygen=97,
        blood_pressure="119/79",
        battery=80,
        source=IngestionSource.SERIAL,
        packet_type="response_ab",
    )

    assert dependencies.is_display_ready_sample(sample, DeviceIngestMode.SERIAL) is True
