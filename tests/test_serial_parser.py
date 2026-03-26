from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.models.health_model import IngestionSource
from iot.parser import T10PacketParser


def _response_a_payload() -> bytes:
    return bytes.fromhex(
        "161803"
        "09E6"
        "5A"
        "0E4A"
        "0048"
        "0062"
        "535708020001"
        "04D2"
    )


def _response_b_payload() -> bytes:
    return bytes.fromhex(
        "160318"
        "78"
        "4E"
        "0E4F"
    )


def _broadcast_payload(sos_value: int = 0x01) -> bytes:
    return bytes.fromhex(
        "0201061AFF4C000215"
        "526164696F6C616E642D541000000000"
        "54"
        "63"
        "0E42"
        f"{sos_value:02X}"
    )


def test_response_a_waits_for_response_b_before_emitting_sample() -> None:
    parser = T10PacketParser()

    first = parser.feed("53:57:08:02:00:01", _response_a_payload(), source=IngestionSource.SERIAL)
    second = parser.feed("53:57:08:02:00:01", _response_b_payload(), source=IngestionSource.SERIAL)

    assert first is None
    assert second is not None
    assert second.device_mac == "53:57:08:02:00:01"
    assert second.heart_rate == 72
    assert second.blood_oxygen == 98
    assert second.temperature == 36.63
    assert second.blood_pressure == "120/78"
    assert second.battery == 90
    assert second.steps == 1234
    assert second.packet_type == "response_ab"
    assert second.raw_packet_a == _response_a_payload().hex().upper()
    assert second.raw_packet_b == _response_b_payload().hex().upper()


def test_response_b_arriving_first_is_merged_when_response_a_arrives() -> None:
    parser = T10PacketParser()

    first = parser.feed("53:57:08:02:00:01", _response_b_payload(), source=IngestionSource.SERIAL)
    second = parser.feed("53:57:08:02:00:01", _response_a_payload(), source=IngestionSource.SERIAL)

    assert first is None
    assert second is not None
    assert second.packet_type == "response_ab"
    assert second.blood_pressure == "120/78"
    assert second.temperature == 36.63


def test_stale_partial_packet_is_not_merged_after_timeout() -> None:
    parser = T10PacketParser(merge_timeout_seconds=0.1)
    base_time = datetime.now(timezone.utc)

    first = parser.feed(
        "53:57:08:02:00:01",
        _response_a_payload(),
        source=IngestionSource.SERIAL,
        timestamp=base_time,
    )
    second = parser.feed(
        "53:57:08:02:00:01",
        _response_b_payload(),
        source=IngestionSource.SERIAL,
        timestamp=base_time + timedelta(seconds=1),
    )

    assert first is None
    # Stale response_a is now flushed as response_a_only (not merged with late response_b)
    assert second is not None
    assert second.packet_type == "response_a_only"
    assert second.heart_rate == 72
    assert second.blood_oxygen == 98
    assert second.steps == 1234
    assert second.blood_pressure is None


def test_broadcast_packet_extracts_sos_fields() -> None:
    parser = T10PacketParser()

    sample = parser.feed("54:10:26:01:00:DF", _broadcast_payload(0x01), source=IngestionSource.SERIAL)

    assert sample is not None
    assert sample.packet_type == "broadcast"
    assert sample.heart_rate == 84
    assert sample.blood_oxygen == 99
    assert sample.temperature == 36.5
    assert sample.sos_flag is True
    assert sample.sos_value == 1
    assert sample.sos_trigger == "double_click"


def test_broadcast_packet_maps_long_press_sos() -> None:
    parser = T10PacketParser()

    sample = parser.feed("54:10:26:01:00:DF", _broadcast_payload(0x02), source=IngestionSource.SERIAL)

    assert sample is not None
    assert sample.sos_flag is True
    assert sample.sos_value == 2
    assert sample.sos_trigger == "long_press"
