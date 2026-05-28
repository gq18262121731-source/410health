from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTING_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_daily_task_routing_001.json"
REPORT_PATH = ROOT / "docs" / "410health_autopilot_triage_note.md"
SUMMARY_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_autopilot_triage_note_001.json"


def _task_summary(task: dict) -> str:
    approval = "yes" if task.get("leader_approval_required") else "no"
    return (
        f"| {task.get('task_id', 'unknown')} | {task.get('owner', 'unknown')} | "
        f"`{task.get('priority', 'unknown')}` | {task.get('reason', 'unknown')} | {approval} |"
    )


def main() -> int:
    routing = json.loads(ROUTING_PATH.read_text(encoding="utf-8"))
    tasks = routing.get("tasks", [])
    blocking_tasks = [task for task in tasks if task.get("priority") == "high"]
    approval_tasks = [task for task in tasks if task.get("leader_approval_required")]
    if blocking_tasks:
        triage_status = "action_required"
        leader_decision_needed = bool(approval_tasks)
        headline = "Autopilot detected blocking work that needs triage."
        recommended_action = blocking_tasks[0].get("action", "Review blocking task.")
    elif approval_tasks:
        triage_status = "approval_required"
        leader_decision_needed = True
        headline = "Autopilot detected work that needs leader approval."
        recommended_action = approval_tasks[0].get("action", "Review approval task.")
    else:
        triage_status = "no_action_required"
        leader_decision_needed = False
        headline = "Autopilot found no blocking issue."
        recommended_action = "Continue normal observation; keep non-blocking warnings in backlog."

    summary = {
        "phase": "SE-2.5",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_routing": str(ROUTING_PATH.relative_to(ROOT)).replace("\\", "/"),
        "triage_status": triage_status,
        "leader_decision_needed": leader_decision_needed,
        "blocking_task_count": len(blocking_tasks),
        "approval_task_count": len(approval_tasks),
        "recommended_next_owner": routing.get("recommended_next_owner", "unknown"),
        "recommended_action": recommended_action,
        "tasks": tasks,
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "\n".join(_task_summary(task) for task in tasks) or "| none | none | `none` | none | no |"
    prohibited = "\n".join(
        [
            "Do not modify business code without approval.",
            "Do not install dependencies without approval.",
            "Do not deploy.",
            "Do not push to remote.",
            "Do not merge branches without approval.",
        ]
    )
    REPORT_PATH.write_text(
        f"""# 410health Autopilot Triage Note

## Summary

```text
phase = SE-2.5
triage_status = {triage_status}
leader_decision_needed = {str(leader_decision_needed).lower()}
blocking_task_count = {len(blocking_tasks)}
approval_task_count = {len(approval_tasks)}
recommended_next_owner = {summary["recommended_next_owner"]}
```

{headline}

## Routed Tasks

| Task | Owner | Priority | Reason | Leader Approval |
| --- | --- | --- | --- | --- |
{rows}

## Recommended Next Action

```text
{recommended_action}
```

## Prohibited Actions

```text
{prohibited}
```

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```
""",
        encoding="utf-8",
    )

    print("410HEALTH AUTOPILOT TRIAGE NOTE")
    print(f"triage_status={triage_status}")
    print(f"leader_decision_needed={str(leader_decision_needed).lower()}")
    print(f"blocking_task_count={len(blocking_tasks)}")
    print(f"report={REPORT_PATH}")
    print(f"summary={SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
