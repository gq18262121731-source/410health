from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROUTING_PATH = Path("evaluations/codebase_residency/410health_daily_task_routing_001.json")
TRIAGE_PATH = Path("evaluations/codebase_residency/410health_autopilot_triage_note_001.json")
OUT_JSON = Path("evaluations/codebase_residency/410health_autonomous_repair_proposal_001.json")
OUT_DOC = Path("docs/410health_autonomous_repair_proposal.md")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    routing = load_json(ROUTING_PATH)
    triage = load_json(TRIAGE_PATH)
    tasks = routing.get("tasks", [])
    blocking_tasks = [task for task in tasks if task.get("blocking")]

    if blocking_tasks:
        status = "proposal_created"
        target_task = blocking_tasks[0].get("task_id", "unknown_blocking_task")
        likely_files = blocking_tasks[0].get("likely_files", [])
        recommended_tests = blocking_tasks[0].get("recommended_tests", ["python scripts/run_410health_daily_autopilot.py"])
        summary = f"Blocking task detected: {target_task}. Generate repair proposal only."
    else:
        status = "no_failure_to_repair"
        target_task = None
        likely_files = []
        recommended_tests = ["python scripts/run_410health_daily_autopilot.py"]
        summary = "Current autopilot is healthy. No repair patch is proposed."

    proposal = {
        "phase": "SE-5.3",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "target_task": target_task,
        "routing_source": str(ROUTING_PATH),
        "triage_source": str(TRIAGE_PATH),
        "leader_approval_required": True,
        "patch_not_applied": True,
        "branch_created": False,
        "commit_attempted": False,
        "push_attempted": False,
        "merge_attempted": False,
        "likely_files": likely_files,
        "recommended_tests": recommended_tests,
        "proposal_summary": summary,
        "allowed_next_action": "leader_review",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    OUT_DOC.write_text(
        "# SE-5.3: Autonomous Repair Proposal\n\n"
        "```text\n"
        f"status = {status}\n"
        f"target_task = {target_task or 'none'}\n"
        "patch_not_applied = true\n"
        "branch_created = false\n"
        "leader_approval_required = true\n"
        "```\n\n"
        f"{summary}\n\n"
        "## Recommended Tests\n\n"
        + "\n".join(f"- `{command}`" for command in recommended_tests)
        + "\n\n## Boundary\n\n"
        "No patch was applied, no source file was changed, no branch was created, and no commit/push/merge was attempted.\n",
        encoding="utf-8",
    )

    print("AUTONOMOUS REPAIR PROPOSAL")
    print(f"status={status}")
    print("patch_not_applied=true")
    print("leader_approval_required=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
