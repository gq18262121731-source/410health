from __future__ import annotations

from datetime import timedelta, timezone

import backend.dependencies as deps
import pytest
from fastapi.testclient import TestClient

from ai.data_generator import SyntheticHealthDataGenerator
from backend.main import app


@pytest.fixture(autouse=True)
def reset_demo_runtime_state():
    deps.get_user_service().reset()
    deps.get_relation_service().reset()
    deps.get_care_service().reset_sessions()
    deps.get_device_service().reset()
    deps.get_stream_service()._streams.clear()
    deps.get_alarm_service()._alarms.clear()
    deps.get_alarm_service()._queue._memory.clear()
    deps.get_alarm_service()._notification_service._push_records.clear()
    deps._baseline_tracker._history.clear()
    deps._intelligent_scorer._device_adapters.clear()
    deps._intelligent_scorer._last_inference_at.clear()
    deps._last_community_alarm_at = None
    yield
    deps.get_user_service().reset()
    deps.get_relation_service().reset()
    deps.get_care_service().reset_sessions()
    deps.get_device_service().reset()
    deps.get_stream_service()._streams.clear()
    deps.get_alarm_service()._alarms.clear()
    deps.get_alarm_service()._queue._memory.clear()
    deps.get_alarm_service()._notification_service._push_records.clear()
    deps._baseline_tracker._history.clear()
    deps._intelligent_scorer._device_adapters.clear()
    deps._intelligent_scorer._last_inference_at.clear()
    deps._last_community_alarm_at = None


def formal_login_headers(client: TestClient, username: str, password: str = "123456") -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_demo_api_flow_covers_registration_login_realtime_evaluation_report_and_alarm() -> None:
    client = TestClient(app)

    elder = client.post(
        "/api/v1/auth/register/elder",
        json={
            "name": "Demo Elder",
            "phone": "13800138201",
            "password": "123456",
            "age": 78,
            "apartment": "20-101",
        },
    )
    assert elder.status_code == 200
    elder_id = elder.json()["id"]

    family = client.post(
        "/api/v1/auth/register/family",
        json={
            "name": "Demo Family",
            "phone": "13900139201",
            "password": "123456",
            "relationship": "daughter",
            "login_username": "demo_family_201",
        },
    )
    assert family.status_code == 200
    family_id = family.json()["id"]

    family_headers = formal_login_headers(client, "demo_family_201")
    elder_headers = formal_login_headers(client, "13800138201")

    family_access_before = client.get("/api/v1/care/access-profile/me", headers=family_headers)
    assert family_access_before.status_code == 200
    assert family_access_before.json()["binding_state"] == "unbound"
    assert family_access_before.json()["capabilities"]["basic_advice"] is True
    assert family_access_before.json()["capabilities"]["device_metrics"] is False

    relation = client.post(
        "/api/v1/relations/family-bind",
        json={
            "elder_user_id": elder_id,
            "family_user_id": family_id,
            "relation_type": "daughter",
            "is_primary": True,
        },
        headers=family_headers,
    )
    assert relation.status_code == 200

    device_mac = "53:57:08:01:02:01"
    device_register = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": device_mac,
            "device_name": "T10-WATCH",
            "user_id": elder_id,
        },
        headers=family_headers,
    )
    assert device_register.status_code == 200
    assert device_register.json()["status"] == "offline"
    assert device_register.json()["bind_status"] == "bound"

    scenario = SyntheticHealthDataGenerator(device_count=1).build_sustained_anomaly_demo_scenario(device_mac=device_mac)

    first_ingest = client.post(
        "/api/v1/health/ingest",
        json=scenario.samples[0].model_dump(mode="json"),
    )
    assert first_ingest.status_code == 200
    assert first_ingest.json()["sample"]["device_mac"] == device_mac

    realtime = client.get(f"/api/v1/health/realtime/{device_mac}")
    assert realtime.status_code == 200
    assert realtime.json()["device_mac"] == device_mac
    assert realtime.json()["health_score"] is not None

    trend = client.get(f"/api/v1/health/trend/{device_mac}?minutes=180&limit=20")
    assert trend.status_code == 200
    assert len(trend.json()) == 1

    last_ingest_payload: dict[str, object] | None = None
    for sample in scenario.samples[1:]:
        response = client.post("/api/v1/health/ingest", json=sample.model_dump(mode="json"))
        assert response.status_code == 200
        last_ingest_payload = response.json()

    assert last_ingest_payload is not None
    assert isinstance(last_ingest_payload["triggered_alarm_ids"], list)
    assert last_ingest_payload["triggered_alarm_ids"]

    family_access_after = client.get("/api/v1/care/access-profile/me", headers=family_headers)
    assert family_access_after.status_code == 200
    family_payload = family_access_after.json()
    assert family_payload["binding_state"] == "bound"
    assert family_payload["capabilities"]["device_metrics"] is True
    assert family_payload["capabilities"]["health_evaluation"] is True
    assert family_payload["capabilities"]["health_report"] is True
    assert family_payload["bound_device_macs"] == [device_mac]
    assert family_payload["related_elder_ids"] == [elder_id]
    assert family_payload["device_metrics"][0]["device_mac"] == device_mac
    assert family_payload["health_evaluations"][0]["device_mac"] == device_mac
    assert family_payload["health_reports"][0]["device_mac"] == device_mac
    assert family_payload["health_reports"][0]["sample_count"] == len(scenario.samples)

    elder_access = client.get("/api/v1/care/access-profile/me", headers=elder_headers)
    assert elder_access.status_code == 200
    assert elder_access.json()["binding_state"] == "bound"
    assert elder_access.json()["bound_device_macs"] == [device_mac]

    intelligent = client.get(f"/api/v1/health/intelligent/{device_mac}")
    assert intelligent.status_code == 200
    intelligent_payload = intelligent.json()
    assert intelligent_payload["ready"] is True
    assert intelligent_payload["probability"] > 0.5
    assert intelligent_payload["score"] > 0

    report = client.post(
        "/api/v1/chat/report/device",
        json={
            "device_mac": device_mac,
            "start_at": (scenario.samples[0].timestamp - timedelta(minutes=1)).astimezone(timezone.utc).isoformat(),
            "end_at": (scenario.samples[-1].timestamp + timedelta(minutes=1)).astimezone(timezone.utc).isoformat(),
            "role": "family",
            "mode": "local",
        },
    )
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["report_type"] == "device_health_report"
    assert report_payload["device_mac"] == device_mac
    assert report_payload["period"]["sample_count"] == len(scenario.samples)
    assert isinstance(report_payload["summary"], str) and report_payload["summary"]
    assert isinstance(report_payload["key_findings"], list) and report_payload["key_findings"]
    assert isinstance(report_payload["recommendations"], list) and report_payload["recommendations"]
    assert "heart_rate" in report_payload["metrics"]

    alarms = client.get("/api/v1/alarms?active_only=true")
    assert alarms.status_code == 200
    active_alarms = alarms.json()
    assert any(item["device_mac"] == device_mac for item in active_alarms)
    assert any(item["alarm_type"] == "intelligent_anomaly" for item in active_alarms)

    queue = client.get("/api/v1/alarms/queue")
    assert queue.status_code == 200
    queue_payload = queue.json()
    assert any(item["alarm"]["device_mac"] == device_mac for item in queue_payload)

    pushes = client.get("/api/v1/alarms/mobile-pushes")
    assert pushes.status_code == 200
    push_payload = pushes.json()
    assert any(item["device_mac"] == device_mac for item in push_payload)
