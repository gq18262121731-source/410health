from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "evaluations" / "codebase_residency"
LATEST_SUMMARY_PATH = SUMMARY_DIR / "410health_daily_autopilot_latest.json"
LEGACY_SUMMARY_PATH = SUMMARY_DIR / "410health_daily_autopilot_001.json"
REPORT_PATH = ROOT / "docs" / "410health_daily_autopilot_report.md"
ROUTING_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_daily_task_routing_001.json"
TRIAGE_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_autopilot_triage_note_001.json"


STEPS = [
    {
        "name": "daily_ops_chain",
        "command": [sys.executable, "scripts/run_410health_daily_ops_chain.py"],
    },
    {
        "name": "task_routing",
        "command": [sys.executable, "scripts/route_410health_daily_tasks.py"],
    },
    {
        "name": "triage_note",
        "command": [sys.executable, "scripts/build_410health_autopilot_triage_note.py"],
    },
]


def _tail(text: str, max_lines: int = 30) -> str:
    return "\n".join((text or "").splitlines()[-max_lines:])


def _run(command: list[str], name: str) -> dict[str, object]:
    started_at = datetime.now(timezone.utc)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_summary_path = SUMMARY_DIR / f"410health_daily_autopilot_{run_id}.json"
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    step_results = [_run(step["command"], step["name"]) for step in STEPS]
    routing = {}
    if ROUTING_PATH.exists():
        routing = json.loads(ROUTING_PATH.read_text(encoding="utf-8"))
    triage = {}
    if TRIAGE_PATH.exists():
        triage = json.loads(TRIAGE_PATH.read_text(encoding="utf-8"))

    blocking_task_count = int(routing.get("blocking_task_count", 0)) if routing else None
    recommended_owner = routing.get("recommended_next_owner", "unknown") if routing else "unknown"
    triage_status = triage.get("triage_status", "unknown") if triage else "unknown"
    leader_decision_needed = bool(triage.get("leader_decision_needed", False)) if triage else False
    all_steps_passed = all(step["status"] == "passed" for step in step_results)
    autopilot_status = "passed" if all_steps_passed and (blocking_task_count in {0, None}) else "needs_attention"

    summary = {
        "phase": "SE-2.6",
        "run_id": run_id,
        "created_at": created_at,
        "project_path": str(ROOT),
        "autopilot_status": autopilot_status,
        "daily_ops_chain": step_results[0]["status"],
        "task_routing": step_results[1]["status"],
        "triage_note": step_results[2]["status"],
        "triage_status": triage_status,
        "leader_decision_needed": leader_decision_needed,
        "blocking_task_count": blocking_task_count,
        "recommended_next_owner": recommended_owner,
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
        "steps": step_results,
        "routing_tasks": routing.get("tasks", []) if routing else [],
        "artifacts": {
            "daily_ops_chain": "evaluations/codebase_residency/410health_daily_ops_chain_001.json",
            "task_routing": "evaluations/codebase_residency/410health_daily_task_routing_001.json",
            "triage_note": "evaluations/codebase_residency/410health_autopilot_triage_note_001.json",
            "autopilot_report": "docs/410health_daily_autopilot_report.md",
            "autopilot_summary": str(run_summary_path.relative_to(ROOT)).replace("\\", "/"),
            "autopilot_latest": str(LATEST_SUMMARY_PATH.relative_to(ROOT)).replace("\\", "/"),
            "autopilot_legacy": str(LEGACY_SUMMARY_PATH.relative_to(ROOT)).replace("\\", "/"),
        },
    }

    summary_text = json.dumps(summary, ensure_ascii=False, indent=2)
    run_summary_path.write_text(summary_text, encoding="utf-8")
    LATEST_SUMMARY_PATH.write_text(summary_text, encoding="utf-8")
    LEGACY_SUMMARY_PATH.write_text(summary_text, encoding="utf-8")

    task_rows = "\n".join(
        "| {task_id} | {owner} | `{priority}` | {reason} |".format(
            task_id=task.get("task_id", "unknown"),
            owner=task.get("owner", "unknown"),
            priority=task.get("priority", "unknown"),
            reason=task.get("reason", "unknown"),
        )
        for task in summary["routing_tasks"]
    ) or "| none | none | `none` | none |"

    REPORT_PATH.write_text(
        f"""# 410health Daily Autopilot Report

## Summary

```text
phase = SE-2.6
run_id = {run_id}
autopilot_status = {autopilot_status}
daily_ops_chain = {summary["daily_ops_chain"]}
task_routing = {summary["task_routing"]}
triage_note = {summary["triage_note"]}
triage_status = {triage_status}
leader_decision_needed = {str(leader_decision_needed).lower()}
blocking_task_count = {blocking_task_count}
recommended_next_owner = {recommended_owner}
```

The daily autopilot ran the Software Open Claw operating chain, task router, and triage note generator in one command.

## Routed Tasks

| Task | Owner | Priority | Reason |
| --- | --- | --- | --- |
{task_rows}

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

    print("410HEALTH DAILY AUTOPILOT")
    print(f"daily_ops_chain={summary['daily_ops_chain']}")
    print(f"task_routing={summary['task_routing']}")
    print(f"triage_note={summary['triage_note']}")
    print(f"triage_status={triage_status}")
    print(f"blocking_task_count={blocking_task_count}")
    print(f"recommended_next_owner={recommended_owner}")
    print(f"autopilot_status={autopilot_status}")
    print(f"report={REPORT_PATH}")
    print(f"summary={run_summary_path}")
    print(f"latest={LATEST_SUMMARY_PATH}")
    return 0 if autopilot_status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
