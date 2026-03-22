from pathlib import Path

from agent.langchain_rag_service import LangChainRAGService
from agent.prompting import build_prompt_package
from agent.prompt_templates import ADVICE_FORMAT_GUIDE, REPORT_FORMAT_GUIDE, ROLE_PROMPTS, SCOPE_PROMPTS
from backend.config import Settings
from backend.models.user_model import UserRole


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "docs" / "knowledge-base"


def test_knowledge_base_markdown_files_are_present_and_readable() -> None:
    files = sorted(KNOWLEDGE_BASE_DIR.glob("*.md"))

    assert len(files) >= 15
    expected_files = {
        "community-care.md",
        "community-report-template.md",
        "community-shift-playbook.md",
        "device-troubleshooting.md",
        "elder-care.md",
        "family-report-template.md",
        "fever-response.md",
        "follow-up-guidance.md",
        "health-report-wording.md",
        "low-oxygen-response.md",
        "report-evidence-writing.md",
        "sos-playbook.md",
        "trend-interpretation.md",
        "vital-sign-thresholds.md",
    }
    assert expected_files.issubset({path.name for path in files})

    for path in files:
        content = path.read_text(encoding="utf-8").strip()
        assert content
        assert "\ufffd" not in content


def test_local_rag_service_reports_documents_and_returns_relevant_hits() -> None:
    service = LangChainRAGService(Settings(), KNOWLEDGE_BASE_DIR)

    stats = service.stats()
    assert stats["retrieval_mode"] == "local_keyword"
    assert stats["offline_only"] is True
    assert stats["document_count"] >= 15
    assert stats["chunk_count"] >= stats["document_count"]

    sos_hits = service.search("SOS 无应答 血氧下降 怎么处理", top_k=2)
    community_hits = service.search("社区 值班 重点巡查 高风险 设备", top_k=2)
    report_hits = service.search("family health report summary weekly report", top_k=3)
    trend_hits = service.search("time series trend interpretation blood oxygen decline report", top_k=3)

    assert sos_hits
    assert community_hits
    assert report_hits
    assert trend_hits
    assert any("sos-playbook.md" in item for item in sos_hits)
    assert any("community-shift-playbook.md" in item or "community-care.md" in item for item in community_hits)
    assert any("family-report-template.md" in item or "report-evidence-writing.md" in item for item in report_hits)
    assert any("trend-interpretation.md" in item or "follow-up-guidance.md" in item for item in trend_hits)


def test_prompt_package_builds_non_empty_sections_for_device_and_community() -> None:
    device_prompt = build_prompt_package(
        role=UserRole.FAMILY,
        scope="device",
        question="Please analyze the recent device data for the family.",
        analysis_context='{"risk_level":"medium"}',
        knowledge_context="[elder-care.md] Continue observation and review the recent oxygen trend.",
    )
    community_prompt = build_prompt_package(
        role=UserRole.COMMUNITY,
        scope="community",
        question="Please summarize community device priorities for the current shift.",
        analysis_context='{"device_count":3}',
        knowledge_context="[community-care.md] Summarize the distribution before the action list.",
    )

    assert device_prompt["system"].strip()
    assert device_prompt["user"].strip()
    assert community_prompt["system"].strip()
    assert community_prompt["user"].strip()
    assert "Respond in Chinese" in device_prompt["system"]
    assert "Return only the final user-visible answer" in community_prompt["user"]


def test_report_prompt_mode_supports_structured_report_generation() -> None:
    family_report_prompt = build_prompt_package(
        role=UserRole.FAMILY,
        scope="device",
        question="Generate a weekly family health report for this elder.",
        analysis_context='{"risk_level":"medium"}',
        knowledge_context="[family-report-template.md] Include summary, key indicators, risk judgment, actions, and uncertainty notes.",
    )
    community_report_prompt = build_prompt_package(
        role=UserRole.COMMUNITY,
        scope="community",
        question="Generate a community shift handoff report.",
        analysis_context='{"device_count":8}',
        knowledge_context="[community-report-template.md] Include overall snapshot, priority list, actions, and handoff notes.",
    )

    assert "Response mode: report" in family_report_prompt["system"]
    assert "structured report" in family_report_prompt["system"]
    assert "daily or weekly care summary" in family_report_prompt["system"]
    assert "shift handoff or patrol report" in community_report_prompt["system"]


def test_prompt_templates_should_be_human_readable() -> None:
    all_prompt_text = "\n".join(
        [
            *ROLE_PROMPTS.values(),
            *SCOPE_PROMPTS.values(),
            *(line for lines in ADVICE_FORMAT_GUIDE.values() for line in lines),
            *(line for lines in REPORT_FORMAT_GUIDE.values() for line in lines),
        ]
    )

    assert "offline family care assistant" in all_prompt_text
    assert "Current scope: single-device analysis" in all_prompt_text
    assert "structured report" in all_prompt_text
    assert "\ufffd" not in all_prompt_text
