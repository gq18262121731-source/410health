from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_daily_residency_check_003.json"
ROUTING_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_daily_task_routing_001.json"
REPORT_PATH = ROOT / "docs" / "410health_daily_task_routing.md"


def _has_chunk_warning(check: dict) -> bool:
    frontend = check.get("checks", {}).get("frontend_check", {})
    return "Some chunks are larger than 500 kB" in (frontend.get("stderr_tail") or "")


def _still_dirty_from_source(status_tail: str) -> bool:
    dirty_paths = []
    for line in (status_tail or "").splitlines():
        if not line.strip():
            continue
        dirty_paths.append(line[3:].strip() if len(line) > 3 else line.strip())
    if not dirty_paths:
        return False

    for path in dirty_paths:
        current = subprocess.run(
            ["git", "status", "--short", "--", path],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if current.stdout.strip():
            return True
    return False


def _route(check: dict) -> list[dict[str, object]]:
    overall = check.get("overall_status", "unknown")
    backend = check.get("backend_status", "unknown")
    frontend = check.get("frontend_status", "unknown")
    git_status = check.get("checks", {}).get("git_status", {})
    git_dirty = _still_dirty_from_source(git_status.get("stdout_tail") or "")
    has_warning = _has_chunk_warning(check)

    tasks: list[dict[str, object]] = []

    if git_dirty:
        tasks.append(
            {
                "task_id": "inspect_dirty_workspace",
                "owner": "safety_officer_lobster",
                "priority": "high",
                "reason": "git_status_has_uncommitted_or_untracked_changes",
                "action": "Inspect changed files before authorizing any code task.",
                "leader_approval_required": False,
            }
        )

    if backend != "passed":
        tasks.append(
            {
                "task_id": "triage_backend_pytest_failure",
                "owner": "qa_reviewer_lobster",
                "priority": "high",
                "reason": "backend_pytest_failed",
                "action": "Classify failing tests and prepare leader approval request before fixing.",
                "leader_approval_required": True,
            }
        )

    if frontend == "failed":
        tasks.append(
            {
                "task_id": "triage_frontend_check_failure",
                "owner": "qa_reviewer_lobster",
                "priority": "high",
                "reason": "frontend_check_failed",
                "action": "Classify typecheck/lint/build failure and request approval before code changes.",
                "leader_approval_required": True,
            }
        )
    elif frontend == "blocked_missing_tooling":
        tasks.append(
            {
                "task_id": "report_frontend_tooling_block",
                "owner": "workflow_engineer_lobster",
                "priority": "medium",
                "reason": "frontend_tooling_missing",
                "action": "Report missing tooling; do not install without leader approval.",
                "leader_approval_required": True,
            }
        )

    if has_warning:
        tasks.append(
            {
                "task_id": "track_vite_chunk_size_warning",
                "owner": "workflow_engineer_lobster",
                "priority": "low",
                "reason": "vite_chunk_size_warning_only",
                "action": "Keep in optimization backlog; do not block daily operations.",
                "leader_approval_required": False,
            }
        )

    if overall == "passed" and not any(task["priority"] == "high" for task in tasks):
        tasks.insert(
            0,
            {
                "task_id": "continue_observation",
                "owner": "workflow_engineer_lobster",
                "priority": "normal",
                "reason": "daily_ops_chain_passed",
                "action": "Continue normal daily Software Open Claw observation.",
                "leader_approval_required": False,
            },
        )

    if not tasks:
        tasks.append(
            {
                "task_id": "manual_review_needed",
                "owner": "product_manager_lobster",
                "priority": "medium",
                "reason": "unclassified_daily_state",
                "action": "Review daily check output and assign next owner.",
                "leader_approval_required": False,
            }
        )
    return tasks


def main() -> int:
    check = json.loads(CHECK_PATH.read_text(encoding="utf-8"))
    tasks = _route(check)
    blocking = [task for task in tasks if task["priority"] == "high"]
    routing = {
        "phase": "SE-2.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_check": str(CHECK_PATH.relative_to(ROOT)).replace("\\", "/"),
        "overall_status": check.get("overall_status", "unknown"),
        "backend_status": check.get("backend_status", "unknown"),
        "frontend_status": check.get("frontend_status", "unknown"),
        "tasks": tasks,
        "task_count": len(tasks),
        "blocking_task_count": len(blocking),
        "recommended_next_owner": tasks[0]["owner"],
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
    }

    ROUTING_PATH.write_text(json.dumps(routing, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "\n".join(
        "| {task_id} | {owner} | `{priority}` | {reason} | {approval} |".format(
            task_id=task["task_id"],
            owner=task["owner"],
            priority=task["priority"],
            reason=task["reason"],
            approval="yes" if task["leader_approval_required"] else "no",
        )
        for task in tasks
    )
    REPORT_PATH.write_text(
        f"""# 410health Daily Task Routing

## Summary

```text
phase = SE-2.1
overall_status = {routing["overall_status"]}
backend_status = {routing["backend_status"]}
frontend_status = {routing["frontend_status"]}
task_count = {routing["task_count"]}
blocking_task_count = {routing["blocking_task_count"]}
recommended_next_owner = {routing["recommended_next_owner"]}
```

The Software Open Claw task router converts the latest daily check into owner-specific next actions.

## Routed Tasks

| Task | Owner | Priority | Reason | Leader Approval |
| --- | --- | --- | --- | --- |
{rows}

## Current Decision

```text
primary_action = {tasks[0]["action"]}
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

    print("410HEALTH DAILY TASK ROUTING")
    print(f"overall_status={routing['overall_status']}")
    print(f"tasks={routing['task_count']}")
    print(f"blocking_tasks={routing['blocking_task_count']}")
    print(f"owner={routing['recommended_next_owner']}")
    print(f"report={REPORT_PATH}")
    print(f"summary={ROUTING_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
