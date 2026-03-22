from agent.response_normalizer import sanitize_agent_response, sanitize_device_health_report, sanitize_text


def test_sanitize_agent_response_removes_meta_prompt_leaks() -> None:
    payload = sanitize_agent_response(
        {
            "answer": """As an AI assistant, I'll break this down.
### Analysis
Here is the result:
Overall status is stable tonight. tool_results: hidden
""",
            "analysis": {
                "risk_flags": ["short heart-rate fluctuation", "short heart-rate fluctuation"],
                "recommendations": ["repeat measurement in 2 hours", "repeat measurement in 2 hours"],
                "notable_events": ["two mild alerts appeared in the last six hours"],
            },
            "references": ["elder-care.md", "elder-care.md"],
        }
    )

    assert payload["answer"] == "Overall status is stable tonight."
    assert payload["analysis"] == {
        "risk_flags": ["short heart-rate fluctuation"],
        "recommendations": ["repeat measurement in 2 hours"],
        "notable_events": ["two mild alerts appeared in the last six hours"],
    }
    assert payload["references"] == ["elder-care.md"]


def test_sanitize_agent_response_builds_fallback_answer_from_analysis() -> None:
    payload = sanitize_agent_response(
        {
            "answer": "### Analysis\nprompt_text: hidden",
            "analysis": {
                "risk_flags": ["short heart-rate fluctuation"],
                "recommendations": ["avoid intense activity"],
                "notable_events": ["two mild alerts appeared in the last six hours"],
            },
            "references": [],
        }
    )

    assert payload["answer"] == "two mild alerts appeared in the last six hours 建议：avoid intense activity"


def test_sanitize_agent_response_preserves_public_community_fields() -> None:
    payload = sanitize_agent_response(
        {
            "answer": "Prioritize the highest-risk device first.",
            "analysis": {
                "risk_distribution": {"high": 1, "medium": 2, "low": 5},
                "priority_devices": [
                    {
                        "device_mac": "53:57:08:01:00:E1",
                        "risk_level": "high",
                        "notable_events": ["repeated abnormal events in the last six hours"],
                    }
                ],
                "recommendations": ["call the highest-risk elder first"],
            },
            "references": ["community-care.md"],
        }
    )

    assert payload["analysis"]["risk_distribution"] == {"high": 1, "medium": 2, "low": 5}
    assert payload["analysis"]["priority_devices"] == [
        {
            "device_mac": "53:57:08:01:00:E1",
            "risk_level": "high",
            "notable_events": ["repeated abnormal events in the last six hours"],
        }
    ]


def test_sanitize_agent_response_removes_english_meta_talk() -> None:
    payload = sanitize_agent_response(
        {
            "answer": """As an AI assistant, I'll break this down.
Here is the result:
Continue observation and encourage hydration.
""",
            "analysis": {},
            "references": [],
        }
    )

    assert payload["answer"] == "Continue observation and encourage hydration."


def test_sanitize_device_health_report_returns_stable_shape() -> None:
    payload = sanitize_device_health_report(
        {
            "report_type": "device_health_report",
            "device_mac": "53:57:08:01:00:E1",
            "subject_name": "Zhang Guilan",
            "device_name": "T10-WATCH",
            "generated_at": "2026-03-21T10:00:00+00:00",
            "period": {
                "start_at": "2026-03-20T10:00:00+00:00",
                "end_at": "2026-03-21T10:00:00+00:00",
                "duration_minutes": 1440,
                "sample_count": 24,
            },
            "summary": "As an AI assistant, I'll break this down.\nOverall status is stable today.",
            "risk_level": "medium",
            "risk_flags": ["short heart-rate fluctuation"],
            "key_findings": ["two mild alerts appeared in the last six hours"],
            "recommendations": ["repeat measurement in 2 hours"],
            "metrics": {
                "heart_rate": {"latest": 88, "average": 82.3, "min": 74, "max": 102, "trend": "stable"},
            },
            "references": ["elder-care.md"],
        }
    )

    assert payload["report_type"] == "device_health_report"
    assert payload["device_mac"] == "53:57:08:01:00:E1"
    assert payload["summary"] == "Overall status is stable today."
    assert payload["period"]["sample_count"] == 24
    assert payload["metrics"]["heart_rate"]["trend"] == "stable"


def test_sanitize_text_removes_markdown_emphasis_and_list_prefixes() -> None:
    cleaned = sanitize_text(
        """**当前概况**
- **风险等级**：中
1. 建议继续观察
"""
    )

    assert "**" not in cleaned
    assert "- " not in cleaned
    assert "1. " not in cleaned
    assert "当前概况" in cleaned
    assert "风险等级：中" in cleaned
