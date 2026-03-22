from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from iot.mqtt_listener import MQTTGatewayListener
from iot.parser import T10PacketParser


BROADCAST_PACKET = "0201061AFF4C000215526164696F6C616E642D54100000000054630E4201"
RESPONSE_A_PACKET = "0A095431302D5741544348141618030ACB640DD400540063535708020001061A"


def test_mqtt_listener_parses_vendor_raw_payload_metadata() -> None:
    listener = MQTTGatewayListener(T10PacketParser())

    envelope = listener.parse_message(f"00535708030001BA{BROADCAST_PACKET}")

    assert envelope is not None
    assert envelope.data_type == "00"
    assert envelope.device_mac == "53:57:08:03:00:01"
    assert envelope.rssi == -70
    assert envelope.hex_payload == BROADCAST_PACKET


def test_mqtt_listener_builds_sample_from_vendor_broadcast_payload() -> None:
    listener = MQTTGatewayListener(T10PacketParser())

    sample = listener.build_sample(f"00535708030001BA{BROADCAST_PACKET}")

    assert sample is not None
    assert sample.source.value == "mqtt"
    assert sample.device_mac == "53:57:08:03:00:01"
    assert sample.packet_type == "broadcast"
    assert sample.heart_rate == 84


def test_mqtt_listener_builds_sample_from_vendor_response_payload() -> None:
    listener = MQTTGatewayListener(T10PacketParser())

    sample = listener.build_sample(f"00535708020001BA{RESPONSE_A_PACKET}")

    assert sample is not None
    assert sample.source.value == "mqtt"
    assert sample.device_mac == "53:57:08:02:00:01"
    assert sample.packet_type == "response_a"
    assert sample.steps == 1562


def test_mqtt_listener_keeps_json_payload_compatibility() -> None:
    listener = MQTTGatewayListener(T10PacketParser())
    payload = json.dumps(
        {
            "device_mac": "53:57:08:03:00:01",
            "hex_payload": BROADCAST_PACKET,
            "rssi": "BA",
        }
    )

    sample = listener.build_sample(payload)

    assert sample is not None
    assert sample.device_mac == "53:57:08:03:00:01"
    assert sample.packet_type == "broadcast"


def test_mqtt_listener_run_invokes_callback_without_asyncio_task(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_payload = f"00535708030001BA{BROADCAST_PACKET}".encode("utf-8")
    received = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            self.on_message = None
            self.connected = None
            self.subscribed = None
            self.auth = None

        def username_pw_set(self, username: str, password: str | None = None) -> None:
            self.auth = (username, password)

        def connect(self, host: str, port: int, keepalive: int) -> None:
            self.connected = (host, port, keepalive)

        def subscribe(self, topic: str) -> None:
            self.subscribed = topic

        def loop_forever(self) -> None:
            message = type("Message", (), {"payload": raw_payload})()
            assert self.on_message is not None
            self.on_message(self, None, message)

    class FakeMQTTModule:
        class CallbackAPIVersion:
            VERSION2 = object()

        Client = FakeClient

    import iot.mqtt_listener as mqtt_listener_module

    monkeypatch.setattr(mqtt_listener_module, "mqtt", FakeMQTTModule)
    listener = MQTTGatewayListener(T10PacketParser())

    listener.run(
        "broker.local",
        1883,
        "gateway/topic",
        username="user",
        password="secret",
        keepalive_seconds=30,
        on_sample=lambda sample: received.append(sample),
    )

    assert len(received) == 1
    assert received[0].packet_type == "broadcast"


def test_system_info_reports_mqtt_mode_flag() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/system/info")

    assert response.status_code == 200
    payload = response.json()
    assert "mqtt_mode" in payload["configured"]
    assert payload["configured"]["mqtt_mode"] is False
