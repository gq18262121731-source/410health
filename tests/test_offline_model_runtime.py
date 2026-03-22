from pathlib import Path
from datetime import datetime, timezone

from agent.langchain_rag_service import LangChainRAGService
from agent.langgraph_health_agent import HealthAgentService
from agent.model_interfaces import AgentModelResult
from backend.config import Settings
from backend.models.health_model import HealthSample
from backend.models.user_model import UserRole


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "docs" / "knowledge-base"


def build_service(**setting_overrides: object) -> HealthAgentService:
    settings = Settings(**setting_overrides)
    rag_service = LangChainRAGService(settings, KNOWLEDGE_BASE_DIR)
    return HealthAgentService(settings, rag_service)


def test_offline_capability_report_exposes_local_only_runtime() -> None:
    service = build_service()

    report = service.capability_report()

    assert report["configured_models"]["execution_mode"] == "local_only"
    assert report["configured_models"]["approved_local_models"] == ["qwen3:1.7b", "deepseek-r1:1.5b"]
    assert report["extensions"]["offline_only_runtime"] is True
    assert report["extensions"]["cloud_mode_enabled"] is False
    assert report["retrieval"]["offline_only"] is True
    assert report["configured_models"]["report_local_model"] == "deepseek-r1:1.5b"
    assert report["configured_models"]["local_report_routing"] == "fixed"


def test_default_settings_do_not_point_supported_runtime_to_cloud_endpoints() -> None:
    settings = Settings(_env_file=None)

    assert settings.offline_only_runtime is True
    assert settings.qwen_api_base == ""
    assert settings.qwen_api_key == ""
    assert settings.qwen_rerank_api == ""
    assert settings.qwen_enable_rerank is False
    assert settings.network_probe_url == ""


def test_local_model_selection_defaults_to_qwen_for_device_analysis() -> None:
    service = build_service(
        local_model_routing="task_router",
        local_default_model="qwen3:1.7b",
        local_reasoning_model="deepseek-r1:1.5b",
        ollama_model="qwen3:1.7b",
    )

    selected = service._select_local_model(
        scope="device",
        question="Analyze recent health data thoroughly.",
        requested_mode="local",
    )

    assert selected == "qwen3:1.7b"


def test_local_model_selection_routes_community_work_to_deepseek() -> None:
    service = build_service(
        local_model_routing="task_router",
        local_default_model="qwen3:1.7b",
        local_reasoning_model="deepseek-r1:1.5b",
        ollama_model="qwen3:1.7b",
    )

    selected = service._select_local_model(
        scope="community",
        question="Summarize community device priorities and explain why.",
        requested_mode="local",
    )

    assert selected == "deepseek-r1:1.5b"


def test_report_model_selection_uses_dedicated_report_route() -> None:
    service = build_service(
        local_report_routing="fixed",
        local_default_model="qwen3:1.7b",
        local_reasoning_model="deepseek-r1:1.5b",
        local_report_model="deepseek-r1:1.5b",
        ollama_model="qwen3:1.7b",
    )

    selected = service._select_report_model(
        role=UserRole.FAMILY,
        requested_mode="local",
    )

    assert selected == "deepseek-r1:1.5b"


def test_single_model_policy_can_switch_default_to_second_approved_model() -> None:
    service = build_service(
        local_model_routing="single",
        local_default_model="deepseek-r1:1.5b",
        local_reasoning_model="deepseek-r1:1.5b",
        ollama_model="deepseek-r1:1.5b",
    )

    selected = service._select_local_model(
        scope="device",
        question="Analyze recent health data thoroughly.",
        requested_mode="local",
    )

    assert selected == "deepseek-r1:1.5b"


def test_local_rag_stays_usable_without_cloud_settings() -> None:
    settings = Settings(qwen_api_key="", network_probe_url="", qwen_enable_rerank=False)
    service = LangChainRAGService(settings, KNOWLEDGE_BASE_DIR)

    hits = service.search(
        "血氧持续偏低应该怎么处理",
        top_k=2,
        network_online=True,
        allow_rerank=True,
    )

    assert hits
    assert any("low-oxygen-response.md" in item or "vital-sign-thresholds.md" in item for item in hits)


def test_dialogue_generate_node_applies_output_limit() -> None:
    service = build_service(dialogue_max_predict_tokens=123, dialogue_max_output_chars=456)
    captured: dict[str, object] = {}

    def fake_invoke_local(prompt_text, messages, **kwargs):
        captured.update(kwargs)
        return "ok"

    service._invoke_local = fake_invoke_local  # type: ignore[method-assign]

    result = service._generate_node(
        {
            "prompt_text": "hello",
            "messages": [],
            "scope": "device",
            "selected_model": "qwen3:1.7b",
            "system_prompt": "",
            "user_prompt": "",
            "analysis_payload": {},
        }
    )

    assert result["answer"] == "ok"
    assert captured["max_predict_tokens"] == 123
    assert captured["max_output_chars"] == 456


def test_report_generation_does_not_apply_dialogue_output_limit() -> None:
    service = build_service(
        dialogue_max_predict_tokens=123,
        dialogue_max_output_chars=456,
        local_report_model="deepseek-r1:1.5b",
        local_report_routing="fixed",
    )
    captured: dict[str, object] = {}

    def fake_invoke_local(prompt_text, messages, **kwargs):
        captured.update(kwargs)
        return "stable report summary"

    service._invoke_local = fake_invoke_local  # type: ignore[method-assign]

    sample = HealthSample(
        device_mac="53:57:08:AA:00:99",
        timestamp=datetime(2026, 3, 22, 3, 0, tzinfo=timezone.utc),
        heart_rate=88,
        temperature=36.7,
        blood_oxygen=97,
        blood_pressure="128/80",
        battery=75,
        health_score=88,
    )

    payload = service.generate_device_health_report(
        role=UserRole.FAMILY,
        device_mac=sample.device_mac,
        start_at=sample.timestamp,
        end_at=sample.timestamp,
        samples=[sample],
        mode="local",
    )

    assert payload["summary"] == "stable report summary"
    assert captured["max_predict_tokens"] is None
    assert captured["max_output_chars"] is None
    assert captured["selected_model"] == "deepseek-r1:1.5b"


def test_report_health_model_signals_include_explicit_health_model_evidence() -> None:
    class DummyModelSuite:
        def run_all(self, model_input):
            assert model_input.question == "health report"
            return {
                "health_assessment": AgentModelResult(
                    model_name="HealthAssessmentModel",
                    status="ok",
                    source="analysis_service",
                    summary="device health assessment summary",
                    payload={"risk_level": "medium"},
                ),
                "risk_scoring": AgentModelResult(
                    model_name="RiskScoringModel",
                    status="ok",
                    source="health_score_service",
                    summary="health score summary",
                    payload={"score": 72},
                ),
                "anomaly_explain": AgentModelResult(
                    model_name="AnomalyExplainModel",
                    status="ok",
                    source="intelligent_scorer",
                    summary="anomaly explain summary",
                    payload={"probability": 0.72, "reason": "blood oxygen falling", "alarm_ready": False},
                ),
                "care_suggestion": AgentModelResult(
                    model_name="CareSuggestionModel",
                    status="ok",
                    source="rule_based",
                    summary="care suggestion summary",
                    payload={"recommendations": ["continue close observation"]},
                ),
                "alarm_interpretation": AgentModelResult(
                    model_name="AlarmInterpretationModel",
                    status="ok",
                    source="alarm_service",
                    summary="alarm interpretation summary",
                    payload={"active_alarm_count": 1},
                ),
            }

    settings = Settings()
    rag_service = LangChainRAGService(settings, KNOWLEDGE_BASE_DIR)
    service = HealthAgentService(settings, rag_service, model_suite=DummyModelSuite())
    sample = HealthSample(
        device_mac="53:57:08:AA:00:98",
        timestamp=datetime(2026, 3, 22, 3, 0, tzinfo=timezone.utc),
        heart_rate=108,
        temperature=37.9,
        blood_oxygen=92,
        blood_pressure="148/92",
        battery=72,
        health_score=72,
    )

    signals = service._build_report_model_signals(
        role=UserRole.FAMILY,
        device_mac=sample.device_mac,
        samples=[sample],
        context_bundle={},
    )

    assert sorted(signals.keys()) == [
        "alarm_interpretation",
        "anomaly_explain",
        "care_suggestion",
        "health_assessment",
        "risk_scoring",
    ]
