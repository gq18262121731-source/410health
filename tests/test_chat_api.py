from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from ai.data_generator import SyntheticHealthDataGenerator
from agent.response_normalizer import sanitize_agent_response, sanitize_device_health_report
from backend.dependencies import get_agent_service, get_stream_service
from backend.main import app
from backend.models.health_model import HealthSample, IngestionSource
from backend.models.user_model import UserRole


BASE_TIME = datetime(2026, 3, 14, 8, 0, tzinfo=timezone.utc)


def build_sample(
    *,
    device_mac: str,
    minutes: int,
    heart_rate: int,
    temperature: float,
    blood_oxygen: int,
    blood_pressure: str,
    health_score: int,
    sos_flag: bool = False,
) -> HealthSample:
    return HealthSample(
        device_mac=device_mac,
        timestamp=BASE_TIME + timedelta(minutes=minutes),
        heart_rate=heart_rate,
        temperature=temperature,
        blood_oxygen=blood_oxygen,
        blood_pressure=blood_pressure,
        battery=76,
        sos_flag=sos_flag,
        source=IngestionSource.MOCK,
        health_score=health_score,
    )


def seed_stream(*samples: HealthSample) -> None:
    stream = get_stream_service()
    for sample in samples:
        stream.publish(sample)


def test_device_analysis_endpoint_returns_structured_payload() -> None:
    device_mac = '53:57:08:AA:00:11'
    seed_stream(
        build_sample(
            device_mac=device_mac,
            minutes=0,
            heart_rate=94,
            temperature=36.8,
            blood_oxygen=96,
            blood_pressure='130/82',
            health_score=84,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=45,
            heart_rate=122,
            temperature=38.1,
            blood_oxygen=90,
            blood_pressure='168/100',
            health_score=60,
            sos_flag=True,
        ),
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/chat/analyze/device',
        json={
            'device_mac': device_mac,
            'question': 'Analyze recent health data thoroughly.',
            'mode': 'local',
            'history_minutes': 60 * 24 * 30,
            'history_limit': 50,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert sorted(payload.keys()) == ['analysis', 'answer', 'references']
    assert isinstance(payload['analysis'], dict)
    assert payload['analysis']['risk_level'] == 'high'
    assert 'scope' not in payload
    assert 'mode' not in payload
    assert 'network_online' not in payload
    assert isinstance(payload['answer'], str) and payload['answer']


def test_community_analysis_endpoint_returns_priority_devices() -> None:
    high_risk_mac = '53:57:08:AA:00:21'
    stable_mac = '53:57:08:AA:00:22'
    seed_stream(
        build_sample(
            device_mac=high_risk_mac,
            minutes=0,
            heart_rate=118,
            temperature=37.9,
            blood_oxygen=91,
            blood_pressure='160/98',
            health_score=64,
        ),
        build_sample(
            device_mac=high_risk_mac,
            minutes=30,
            heart_rate=126,
            temperature=38.4,
            blood_oxygen=88,
            blood_pressure='172/108',
            health_score=55,
            sos_flag=True,
        ),
        build_sample(
            device_mac=stable_mac,
            minutes=0,
            heart_rate=75,
            temperature=36.5,
            blood_oxygen=98,
            blood_pressure='122/78',
            health_score=91,
        ),
        build_sample(
            device_mac=stable_mac,
            minutes=30,
            heart_rate=76,
            temperature=36.6,
            blood_oxygen=97,
            blood_pressure='124/80',
            health_score=89,
        ),
    )

    client = TestClient(app)
    response = client.post(
        '/api/v1/chat/analyze/community',
        json={
            'question': 'Summarize recent health data across community devices.',
            'mode': 'local',
            'history_minutes': 60 * 24 * 30,
            'per_device_limit': 50,
            'device_macs': [high_risk_mac, stable_mac],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert sorted(payload.keys()) == ['analysis', 'answer', 'references']
    assert isinstance(payload['analysis'], dict)
    assert payload['analysis']['device_count'] == 2
    assert payload['analysis']['risk_distribution']['high'] == 1
    assert payload['analysis']['priority_devices'][0]['device_mac'] == high_risk_mac
    assert isinstance(payload['answer'], str) and payload['answer']


def test_health_model_report_evidence_distinguishes_single_vs_sustained_abnormality() -> None:
    generator = SyntheticHealthDataGenerator(device_count=1)
    service = get_agent_service()
    scenario = generator.build_sustained_anomaly_demo_scenario(start=BASE_TIME)
    scorer = service._model_suite._models["anomaly_explain"]._scorer
    scorer.warmup(generator.build_training_sequences(hours=6, step_minutes=10))

    early_samples = scenario.samples[:7]
    full_samples = scenario.samples

    early_analysis = service._analysis.summarize_device(early_samples)
    full_analysis = service._analysis.summarize_device(full_samples)
    early_signals = service._build_report_model_signals(
        role=UserRole.FAMILY,
        device_mac=scenario.device_mac,
        samples=early_samples,
        context_bundle={},
    )
    full_signals = service._build_report_model_signals(
        role=UserRole.FAMILY,
        device_mac=scenario.device_mac,
        samples=full_samples,
        context_bundle={},
    )
    early_evidence = service._build_report_health_model_evidence(
        device_mac=scenario.device_mac,
        samples=early_samples,
        analysis_payload=early_analysis,
        model_signals=early_signals,
    )
    full_evidence = service._build_report_health_model_evidence(
        device_mac=scenario.device_mac,
        samples=full_samples,
        analysis_payload=full_analysis,
        model_signals=full_signals,
    )

    assert early_evidence["evidence_version"] == "hm_report_v2"
    assert early_evidence["input_window"]["transformer_window"] == 6
    assert early_evidence["input_window"]["feature_names"] == ["heart_rate", "temperature", "blood_oxygen", "systolic"]
    assert early_evidence["anomaly_stage"] == "abnormal"
    assert early_evidence["sustained_abnormality"]["alarm_ready"] is False
    assert full_evidence["anomaly_stage"] == "alarm"
    assert full_evidence["sustained_abnormality"]["alarm_ready"] is True
    assert full_evidence["key_evidence"]
    assert full_evidence["summary_inputs"]
    assert "health_assessment" in full_evidence["model_payloads"]
    assert "anomaly_explain" in full_evidence["model_payloads"]


def test_device_health_report_prompt_context_includes_health_model_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = SyntheticHealthDataGenerator(device_count=1)
    service = get_agent_service()
    scenario = generator.build_sustained_anomaly_demo_scenario(start=BASE_TIME)
    scorer = service._model_suite._models["anomaly_explain"]._scorer
    scorer.warmup(generator.build_training_sequences(hours=6, step_minutes=10))
    seed_stream(*scenario.samples)

    captured: dict[str, str] = {}

    def capture_invoke(prompt_text: str, *args, **kwargs):
        captured["prompt_text"] = prompt_text
        return ""

    monkeypatch.setattr(service, "_invoke_local", capture_invoke)

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/report/device",
        json={
            "device_mac": scenario.device_mac,
            "start_at": (BASE_TIME - timedelta(minutes=5)).isoformat(),
            "end_at": (BASE_TIME + timedelta(minutes=120)).isoformat(),
            "mode": "local",
        },
    )

    assert response.status_code == 200
    assert "health_model_evidence" in captured["prompt_text"]
    payload = response.json()
    assert sorted(payload.keys()) == [
        "device_mac",
        "device_name",
        "generated_at",
        "key_findings",
        "metrics",
        "period",
        "recommendations",
        "references",
        "report_type",
        "risk_flags",
        "risk_level",
        "subject_name",
        "summary",
    ]


@pytest.mark.xfail(
    reason="Quality risk: fallback report copy still leaks low-quality mixed metric keys into public prose.",
    strict=False,
)
def test_device_health_report_fallback_copy_should_not_mix_internal_metric_keys_into_public_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_mac = "53:57:08:AA:00:67"
    seed_stream(
        build_sample(
            device_mac=device_mac,
            minutes=0,
            heart_rate=84,
            temperature=36.6,
            blood_oxygen=96,
            blood_pressure="126/82",
            health_score=86,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=60,
            heart_rate=98,
            temperature=37.8,
            blood_oxygen=92,
            blood_pressure="142/88",
            health_score=71,
        ),
    )

    service = get_agent_service()
    monkeypatch.setattr(service, "_invoke_local", lambda *_, **__: "")
    monkeypatch.setattr(service._rag, "search", lambda *_, **__: [])

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/report/device",
        json={
            "device_mac": device_mac,
            "start_at": (BASE_TIME - timedelta(minutes=5)).isoformat(),
            "end_at": (BASE_TIME + timedelta(minutes=90)).isoformat(),
            "mode": "local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    public_text = " ".join([payload["summary"], *payload["key_findings"], *payload["recommendations"]])
    assert "heart_rate" not in public_text
    assert "blood_oxygen" not in public_text
    assert "health_score" not in public_text


@pytest.mark.parametrize(
    ("path", "payload", "expected_fragment"),
    [
        (
            "/api/v1/chat/analyze/device",
            {
                "device_mac": "53:57:08:AA:00:31",
                "question": "Analyze recent health data thoroughly.",
                "role": "visitor",
                "mode": "local",
            },
            "role",
        ),
        (
            "/api/v1/chat/analyze/device",
            {
                "device_mac": "53:57:08:AA:00:31",
                "question": "Analyze recent health data thoroughly.",
                "role": "family",
                "mode": "remote",
            },
            "mode",
        ),
        (
            "/api/v1/chat/analyze/device",
            {
                "device_mac": "53:57:08:AA:00:31",
                "question": "Analyze recent health data thoroughly.",
                "history_minutes": 29,
            },
            "history_minutes",
        ),
        (
            "/api/v1/chat/analyze/device",
            {
                "device_mac": "53:57:08:AA:00:31",
                "question": "Analyze recent health data thoroughly.",
                "history_limit": 11,
            },
            "history_limit",
        ),
        (
            "/api/v1/chat/analyze/community",
            {
                "question": "Summarize recent health data across community devices.",
                "role": "guest",
                "mode": "local",
            },
            "role",
        ),
        (
            "/api/v1/chat/analyze/community",
            {
                "question": "Summarize recent health data across community devices.",
                "role": "community",
                "mode": "remote",
            },
            "mode",
        ),
        (
            "/api/v1/chat/analyze/community",
            {
                "question": "Summarize recent health data across community devices.",
                "per_device_limit": 1001,
            },
            "per_device_limit",
        ),
    ],
)
def test_analysis_endpoints_reject_invalid_request_shapes(
    path: str,
    payload: dict[str, object],
    expected_fragment: str,
) -> None:
    client = TestClient(app)

    response = client.post(path, json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(expected_fragment in ".".join(str(part) for part in item["loc"]) for item in detail)


def test_device_analysis_endpoint_supports_answer_without_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    service = get_agent_service()
    monkeypatch.setattr(
        service,
        "analyze_device",
        lambda **_: sanitize_agent_response(
            {
                "answer": "Continue hydration and close observation tonight.",
                "references": ["care-playbook.md"],
            }
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/analyze/device",
        json={
            "device_mac": "53:57:08:AA:00:41",
            "question": "What should the family watch for tonight?",
            "mode": "local",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Continue hydration and close observation tonight.",
        "analysis": {
            "risk_flags": [],
            "recommendations": [],
            "notable_events": [],
        },
        "references": ["care-playbook.md"],
    }


def test_community_analysis_endpoint_normalizes_partial_analysis_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    service = get_agent_service()
    monkeypatch.setattr(
        service,
        "analyze_community",
        lambda **_: sanitize_agent_response(
            {
                "answer": "Prioritize one high-risk device for follow-up.",
                "analysis": {
                    "device_count": 2,
                    "risk_distribution": {"high": 1, "medium": 1, "ignored": 99},
                    "priority_devices": [
                        {
                            "device_mac": "53:57:08:AA:00:51",
                            "risk_level": "high",
                            "notable_events": ["Repeated fever trend"],
                            "debug_note": "hidden",
                        }
                    ],
                },
                "references": [],
            }
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/analyze/community",
        json={
            "question": "Summarize recent health data across community devices.",
            "mode": "local",
            "device_macs": ["53:57:08:AA:00:51", "53:57:08:AA:00:52"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Prioritize one high-risk device for follow-up."
    assert payload["analysis"] == {
        "risk_flags": [],
        "recommendations": [],
        "notable_events": [],
        "device_count": 2,
        "risk_distribution": {"high": 1, "medium": 1},
        "priority_devices": [
            {
                "device_mac": "53:57:08:AA:00:51",
                "risk_level": "high",
                "notable_events": ["Repeated fever trend"],
            }
        ],
    }
    assert payload["references"] == []


def test_device_health_report_endpoint_returns_stable_report_shape() -> None:
    device_mac = "53:57:08:AA:00:61"
    seed_stream(
        build_sample(
            device_mac=device_mac,
            minutes=0,
            heart_rate=84,
            temperature=36.7,
            blood_oxygen=97,
            blood_pressure="128/80",
            health_score=86,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=60,
            heart_rate=96,
            temperature=37.6,
            blood_oxygen=94,
            blood_pressure="138/86",
            health_score=76,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=120,
            heart_rate=108,
            temperature=38.1,
            blood_oxygen=92,
            blood_pressure="148/92",
            health_score=68,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/report/device",
        json={
            "device_mac": device_mac,
            "start_at": (BASE_TIME - timedelta(minutes=5)).isoformat(),
            "end_at": (BASE_TIME + timedelta(minutes=180)).isoformat(),
            "mode": "local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert sorted(payload.keys()) == [
        "device_mac",
        "device_name",
        "generated_at",
        "key_findings",
        "metrics",
        "period",
        "recommendations",
        "references",
        "report_type",
        "risk_flags",
        "risk_level",
        "subject_name",
        "summary",
    ]
    assert payload["report_type"] == "device_health_report"
    assert payload["device_mac"] == device_mac
    assert payload["period"]["sample_count"] == 3
    assert payload["risk_level"] in {"medium", "high"}
    assert isinstance(payload["summary"], str) and payload["summary"]
    assert isinstance(payload["key_findings"], list)
    assert isinstance(payload["recommendations"], list)
    assert "heart_rate" in payload["metrics"]
    assert "references" in payload
    assert "answer" not in payload
    assert "analysis" not in payload


def test_report_route_does_not_call_dialogue_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    service = get_agent_service()
    calls = {"report": 0}

    def fail_dialogue(**_kwargs):
        raise AssertionError("Dialogue handlers must not be called by /chat/report/device")

    def fake_report(**kwargs):
        calls["report"] += 1
        assert kwargs["device_mac"] == "53:57:08:AA:00:64"
        return sanitize_device_health_report(
            {
                "report_type": "device_health_report",
                "device_mac": "53:57:08:AA:00:64",
                "subject_name": "Report Route Subject",
                "device_name": "T10-WATCH",
                "generated_at": BASE_TIME.isoformat(),
                "period": {
                    "start_at": BASE_TIME.isoformat(),
                    "end_at": (BASE_TIME + timedelta(minutes=30)).isoformat(),
                    "duration_minutes": 30,
                    "sample_count": 0,
                },
                "summary": "Dedicated report route response.",
                "risk_level": "low",
                "risk_flags": [],
                "key_findings": [],
                "recommendations": [],
                "metrics": {},
                "references": [],
            }
        )

    monkeypatch.setattr(service, "analyze_device", fail_dialogue)
    monkeypatch.setattr(service, "analyze_community", fail_dialogue)
    monkeypatch.setattr(service, "generate_device_health_report", fake_report)

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/report/device",
        json={
            "device_mac": "53:57:08:AA:00:64",
            "start_at": BASE_TIME.isoformat(),
            "end_at": (BASE_TIME + timedelta(minutes=30)).isoformat(),
            "mode": "local",
        },
    )

    assert response.status_code == 200
    assert calls["report"] == 1
    assert response.json()["summary"] == "Dedicated report route response."


def test_dialogue_route_does_not_call_report_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    service = get_agent_service()

    def fail_report(**_kwargs):
        raise AssertionError("Report generator must not be called by dialogue routes")

    monkeypatch.setattr(service, "generate_device_health_report", fail_report)
    monkeypatch.setattr(
        service,
        "analyze_device",
        lambda **_: sanitize_agent_response(
            {
                "answer": "Dialogue route stayed on analyze_device.",
                "references": ["elder-care.md"],
                "analysis": {"risk_level": "low"},
            }
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/analyze/device",
        json={
            "device_mac": "53:57:08:AA:00:65",
            "question": "What should I watch today?",
            "mode": "local",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Dialogue route stayed on analyze_device."


def test_device_health_report_endpoint_includes_report_oriented_references_and_clean_summary() -> None:
    device_mac = "53:57:08:AA:00:62"
    seed_stream(
        build_sample(
            device_mac=device_mac,
            minutes=0,
            heart_rate=88,
            temperature=36.8,
            blood_oxygen=96,
            blood_pressure="128/82",
            health_score=84,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=90,
            heart_rate=102,
            temperature=37.8,
            blood_oxygen=93,
            blood_pressure="142/88",
            health_score=72,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=180,
            heart_rate=112,
            temperature=38.2,
            blood_oxygen=91,
            blood_pressure="148/92",
            health_score=66,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/report/device",
        json={
            "device_mac": device_mac,
            "start_at": (BASE_TIME - timedelta(minutes=5)).isoformat(),
            "end_at": (BASE_TIME + timedelta(minutes=240)).isoformat(),
            "role": "family",
            "mode": "local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "prompt" not in payload["summary"].lower()
    assert "tool_results" not in payload["summary"]
    assert "blood_oxygen" not in payload["summary"]
    assert "rising" not in payload["summary"]
    assert "falling" not in payload["summary"]
    assert any("时序模型" in item or "健康评分" in item for item in payload["key_findings"])
    assert any(
        "family-report-template.md" in item
        or "report-evidence-writing.md" in item
        or "follow-up-guidance.md" in item
        for item in payload["references"]
    )


def test_device_health_report_output_reflects_health_score_trend_and_sustained_anomaly_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_mac = "53:57:08:AA:00:66"
    seed_stream(
        build_sample(
            device_mac=device_mac,
            minutes=0,
            heart_rate=76,
            temperature=36.5,
            blood_oxygen=97,
            blood_pressure="120/80",
            health_score=91,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=30,
            heart_rate=88,
            temperature=37.2,
            blood_oxygen=94,
            blood_pressure="132/84",
            health_score=79,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=60,
            heart_rate=102,
            temperature=37.8,
            blood_oxygen=92,
            blood_pressure="144/90",
            health_score=68,
        ),
        build_sample(
            device_mac=device_mac,
            minutes=90,
            heart_rate=116,
            temperature=38.2,
            blood_oxygen=89,
            blood_pressure="156/96",
            health_score=58,
        ),
    )

    service = get_agent_service()
    monkeypatch.setattr(service, "_invoke_local", lambda *_, **__: "")
    monkeypatch.setattr(service._rag, "search", lambda *_, **__: [])
    monkeypatch.setattr(
        service,
        "_build_report_model_signals",
        lambda **_: {
            "anomaly_explain": {
                "payload": {
                    "probability": 0.83,
                    "reason": "持续低氧与体温上升",
                    "sustained_minutes": 40,
                    "alarm_ready": True,
                }
            }
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/report/device",
        json={
            "device_mac": device_mac,
            "start_at": (BASE_TIME - timedelta(minutes=5)).isoformat(),
            "end_at": (BASE_TIME + timedelta(minutes=120)).isoformat(),
            "mode": "local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] == "high"
    assert payload["metrics"]["health_score"]["latest"] == 58
    assert payload["metrics"]["health_score"]["trend"] == "falling"
    assert payload["metrics"]["blood_oxygen"]["latest"] == 89
    assert payload["metrics"]["blood_oxygen"]["trend"] == "falling"
    assert payload["metrics"]["temperature"]["trend"] == "rising"
    assert any("40" in item and "持续" in item for item in payload["key_findings"])
    assert any("告警" in item or "复核" in item for item in payload["recommendations"])


def test_device_health_report_fallback_summary_uses_transformer_model_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_mac = "53:57:08:AA:00:63"
    for minutes, heart_rate, temperature, blood_oxygen, blood_pressure, health_score in [
        (0, 74, 36.5, 97, "120/80", 90),
        (10, 75, 36.6, 97, "121/80", 89),
        (20, 73, 36.5, 98, "119/79", 90),
        (30, 76, 36.6, 97, "121/80", 88),
        (40, 74, 36.5, 97, "120/80", 89),
        (50, 75, 36.5, 97, "121/80", 88),
        (60, 88, 37.1, 94, "132/84", 80),
        (70, 98, 37.6, 92, "146/90", 73),
        (80, 108, 37.8, 91, "152/94", 68),
        (90, 116, 38.0, 90, "160/96", 62),
    ]:
        seed_stream(
            build_sample(
                device_mac=device_mac,
                minutes=minutes,
                heart_rate=heart_rate,
                temperature=temperature,
                blood_oxygen=blood_oxygen,
                blood_pressure=blood_pressure,
                health_score=health_score,
            )
        )

    service = get_agent_service()
    monkeypatch.setattr(service, "_invoke_local", lambda *_, **__: "")

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/report/device",
        json={
            "device_mac": device_mac,
            "start_at": (BASE_TIME - timedelta(minutes=5)).isoformat(),
            "end_at": (BASE_TIME + timedelta(minutes=120)).isoformat(),
            "mode": "local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "时序模型" in payload["summary"]
    assert any("时序模型" in item for item in payload["key_findings"])
    assert any("时序模型" in item for item in payload["recommendations"])


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        (
            {
                "device_mac": "53:57:08:AA:00:61",
                "start_at": BASE_TIME.isoformat(),
                "end_at": BASE_TIME.isoformat(),
                "mode": "local",
            },
            "end_at",
        ),
        (
            {
                "device_mac": "53:57:08:AA:00:61",
                "start_at": BASE_TIME.isoformat(),
                "end_at": (BASE_TIME + timedelta(minutes=30)).isoformat(),
                "role": "visitor",
                "mode": "local",
            },
            "role",
        ),
        (
            {
                "device_mac": "53:57:08:AA:00:61",
                "start_at": BASE_TIME.isoformat(),
                "end_at": (BASE_TIME + timedelta(minutes=30)).isoformat(),
                "mode": "remote",
            },
            "mode",
        ),
    ],
)
def test_device_health_report_endpoint_rejects_invalid_request_shapes(
    payload: dict[str, object],
    expected_fragment: str,
) -> None:
    client = TestClient(app)
    response = client.post("/api/v1/chat/report/device", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    if isinstance(detail, list):
        assert any(
            expected_fragment in ".".join(str(part) for part in item["loc"])
            or expected_fragment in str(item.get("msg", ""))
            for item in detail
        )
    else:
        assert expected_fragment in str(detail)
