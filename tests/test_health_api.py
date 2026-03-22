from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.dependencies import get_stream_service
from backend.models.health_model import HealthSample
from backend.main import app


def test_healthz() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_community_overview_contains_macro_fields() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health/community/overview")

    assert response.status_code == 200
    payload = response.json()
    assert "clusters" in payload
    assert "trend" in payload
    assert "risk_heatmap" in payload
    assert isinstance(payload["risk_heatmap"], list)


def test_alarm_queue_and_mobile_push_endpoints() -> None:
    client = TestClient(app)

    queue_response = client.get("/api/v1/alarms/queue")
    push_response = client.get("/api/v1/alarms/mobile-pushes")

    assert queue_response.status_code == 200
    assert push_response.status_code == 200
    assert isinstance(queue_response.json(), list)
    assert isinstance(push_response.json(), list)


def test_intelligent_health_endpoint_keeps_existing_output_fields() -> None:
    client = TestClient(app)
    stream = get_stream_service()
    device_mac = "53:57:08:AA:00:91"
    base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    for index, (heart_rate, temperature, blood_oxygen, systolic) in enumerate(
        [
            (74, 36.5, 97, 120),
            (75, 36.6, 97, 121),
            (73, 36.5, 98, 119),
            (76, 36.6, 97, 121),
            (88, 37.2, 94, 132),
            (98, 37.7, 92, 146),
        ]
    ):
        stream.publish(
            HealthSample(
                device_mac=device_mac,
                timestamp=base_time + timedelta(minutes=index * 10),
                heart_rate=heart_rate,
                temperature=temperature,
                blood_oxygen=blood_oxygen,
                blood_pressure=f"{systolic}/88",
                battery=70,
            )
        )

    response = client.get(f"/api/v1/health/intelligent/{device_mac}")

    assert response.status_code == 200
    payload = response.json()
    assert sorted(payload.keys()) == [
        "device_mac",
        "drift_score",
        "probability",
        "ready",
        "reason",
        "reconstruction_score",
        "score",
    ]
