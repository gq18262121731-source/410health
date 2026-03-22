from __future__ import annotations

import json
from pathlib import Path

from iot.mqtt_listener import MQTTGatewayListener
from iot.parser import T10PacketParser


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gateway_http"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_gateway_http_candidate_fixtures_keep_messagepack_devices_array_shape() -> None:
    fixture_names = sorted(path.name for path in FIXTURE_DIR.glob("gateway_http_*.json"))

    assert fixture_names == [
        "gateway_http_broadcast_devices_array.json",
        "gateway_http_malformed_devices_array.json",
        "gateway_http_response_merge_devices_array.json",
    ]

    for fixture_name in fixture_names:
        payload = load_fixture(fixture_name)
        metadata = payload["fixture_metadata"]
        body = payload["body"]

        assert metadata["transport_encoding"] == "messagepack_candidate"
        assert metadata["planned_content_type"] == "application/msgpack"
        assert isinstance(body["devices"], list)
        assert body["devices"]


def test_gateway_http_broadcast_fixture_parses_to_expected_sample() -> None:
    fixture = load_fixture("gateway_http_broadcast_devices_array.json")
    device = fixture["body"]["devices"][0]
    expected = fixture["expected"]["samples"][0]
    listener = MQTTGatewayListener(T10PacketParser())

    sample = listener.build_sample(device["raw_payload"])

    assert sample is not None
    assert sample.device_mac == expected["device_mac"]
    assert sample.packet_type == expected["packet_type"]
    assert sample.heart_rate == expected["heart_rate"]
    assert sample.blood_oxygen == expected["blood_oxygen"]
    assert sample.temperature == expected["temperature"]
    assert sample.sos_flag is expected["sos_flag"]


def test_gateway_http_response_merge_fixture_reaches_response_ab() -> None:
    fixture = load_fixture("gateway_http_response_merge_devices_array.json")
    listener = MQTTGatewayListener(T10PacketParser())
    final_sample = None

    for device in fixture["body"]["devices"]:
        final_sample = listener.build_sample(device["raw_payload"])

    expected = fixture["expected"]["final_sample"]
    assert final_sample is not None
    assert final_sample.device_mac == expected["device_mac"]
    assert final_sample.packet_type == expected["packet_type"]
    assert final_sample.blood_pressure == expected["blood_pressure"]
    assert final_sample.temperature == expected["temperature"]
    assert final_sample.heart_rate == expected["heart_rate"]
    assert final_sample.blood_oxygen == expected["blood_oxygen"]


def test_gateway_http_malformed_fixture_stays_parser_safe() -> None:
    fixture = load_fixture("gateway_http_malformed_devices_array.json")
    listener = MQTTGatewayListener(T10PacketParser())

    samples = [listener.build_sample(device["raw_payload"]) for device in fixture["body"]["devices"]]

    assert samples == [None]
