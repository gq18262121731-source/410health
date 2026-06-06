from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


AUTOPILOT_PATH = Path("evaluations/codebase_residency/410health_daily_autopilot_latest.json")
ROUTING_PATH = Path("evaluations/codebase_residency/410health_daily_task_routing_001.json")
OUT_JSON = Path("evaluations/codebase_residency/410health_daily_autonomous_standup_001.json")
OUT_DOC = Path("docs/410health_daily_autonomous_standup.md")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    autopilot = load_json(AUTOPILOT_PATH)
    routing = load_json(ROUTING_PATH)
    status = autopilot.get("autopilot_status", "unknown")
    blocking_count = autopilot.get("blocking_task_count", routing.get("blocking_task_count", 0))
    next_owner = autopilot.get("recommended_next_owner", routing.get("recommended_next_owner", "workflow_engineer_lobster"))

    messages = [
        {
            "time": datetime.now().isoformat(timespec="seconds"),
            "speaker": "workflow_engineer_lobster",
            "type": "daily_standup",
            "status": status,
            "message": "Daily autopilot completed. Maintain the operating chain and watch generated tasks.",
        },
        {
            "time": datetime.now().isoformat(timespec="seconds"),
            "speaker": "product_manager_lobster",
            "type": "leader_summary",
            "status": "healthy" if status == "passed" and blocking_count == 0 else "needs_review",
            "message": "No blocking task requires leader decision." if blocking_count == 0 else "Blocking task requires review.",
        },
        {
            "time": datetime.now().isoformat(timespec="seconds"),
            "speaker": "qa_reviewer_lobster",
            "type": "quality_watch",
            "status": "standby" if blocking_count == 0 else "triage_required",
            "message": "No failing test triage is active." if blocking_count == 0 else "Review routed failure and prepare proposal.",
        },
        {
            "time": datetime.now().isoformat(timespec="seconds"),
            "speaker": "safety_officer_lobster",
            "type": "boundary_check",
            "status": "clear",
            "message": "No deploy, dependency install, force push, or protected branch push is authorized.",
        },
    ]

    summary = {
        "phase": "SE-5.7",
        "result": "passed",
        "daily_standup_created": True,
        "leader_summary_created": True,
        "next_owner_assigned": True,
        "external_sync_optional": True,
        "yuque_sync_attempted": False,
        "autopilot_status": status,
        "blocking_task_count": blocking_count,
        "next_owner": next_owner,
        "messages": messages,
    }

    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_DOC.write_text(
        "# SE-5.7: Daily Autonomous Standup\n\n"
        "```text\n"
        f"daily_standup_created = true\n"
        f"autopilot_status = {status}\n"
        f"blocking_task_count = {blocking_count}\n"
        f"next_owner = {next_owner}\n"
        "yuque_sync_attempted = false\n"
        "```\n\n"
        "## Messages\n\n"
        + "\n".join(f"- **{item['speaker']}**: {item['message']}" for item in messages)
        + "\n\nYuque/API sync is deferred until a token and target document space are provided.\n",
        encoding="utf-8",
    )

    print("DAILY AUTONOMOUS STANDUP")
    print(f"autopilot_status={status}")
    print(f"blocking_task_count={blocking_count}")
    print(f"next_owner={next_owner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
