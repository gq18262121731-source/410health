from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "evaluations" / "codebase_residency"
REPORT_PATH = ROOT / "docs" / "410health_autopilot_history_summary.md"
SUMMARY_PATH = SOURCE_DIR / "410health_autopilot_history_summary.json"
RUN_PATTERN = re.compile(r"410health_daily_autopilot_(\d{8}_\d{6})\.json$")


def _load_runs() -> list[dict]:
    runs = []
    for path in sorted(SOURCE_DIR.glob("410health_daily_autopilot_*.json")):
        match = RUN_PATTERN.match(path.name)
        if not match:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        runs.append(
            {
                "run_id": data.get("run_id", match.group(1)),
                "source_file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "created_at": data.get("created_at", ""),
                "autopilot_status": data.get("autopilot_status", "unknown"),
                "daily_ops_chain": data.get("daily_ops_chain", "unknown"),
                "task_routing": data.get("task_routing", "unknown"),
                "triage_note": data.get("triage_note", "unknown"),
                "triage_status": data.get("triage_status", "unknown"),
                "leader_decision_needed": data.get("leader_decision_needed", False),
                "blocking_task_count": data.get("blocking_task_count", None),
                "recommended_next_owner": data.get("recommended_next_owner", "unknown"),
            }
        )
    return runs


def _trend(runs: list[dict]) -> str:
    if not runs:
        return "no_data"
    latest = runs[-1]
    if latest["autopilot_status"] != "passed" or latest["blocking_task_count"]:
        return "needs_attention"
    if len(runs) == 1:
        return "stable"
    recent = runs[-3:]
    if all(run["autopilot_status"] == "passed" and not run["blocking_task_count"] for run in recent):
        return "stable"
    return "improving"


def main() -> int:
    runs = _load_runs()
    latest = runs[-1] if runs else {}
    status_counts = Counter(run["autopilot_status"] for run in runs)
    blocking_runs = [run for run in runs if run.get("blocking_task_count")]
    leader_runs = [run for run in runs if run.get("leader_decision_needed")]
    summary = {
        "phase": "SE-2.8",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_count": len(runs),
        "latest_run_id": latest.get("run_id", "none"),
        "latest_status": latest.get("autopilot_status", "none"),
        "latest_blocking_task_count": latest.get("blocking_task_count", None),
        "latest_leader_decision_needed": latest.get("leader_decision_needed", False),
        "latest_owner": latest.get("recommended_next_owner", "none"),
        "trend": _trend(runs),
        "status_counts": dict(status_counts),
        "blocking_run_count": len(blocking_runs),
        "leader_decision_run_count": len(leader_runs),
        "runs": runs,
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "\n".join(
        "| {run_id} | `{status}` | {blocking} | {leader} | {owner} |".format(
            run_id=run["run_id"],
            status=run["autopilot_status"],
            blocking=run["blocking_task_count"],
            leader="yes" if run["leader_decision_needed"] else "no",
            owner=run["recommended_next_owner"],
        )
        for run in runs[-10:]
    ) or "| none | `none` | none | no | none |"

    REPORT_PATH.write_text(
        f"""# 410health Autopilot History Summary

## Summary

```text
phase = SE-2.8
run_count = {summary["run_count"]}
latest_run_id = {summary["latest_run_id"]}
latest_status = {summary["latest_status"]}
latest_blocking_task_count = {summary["latest_blocking_task_count"]}
latest_leader_decision_needed = {str(summary["latest_leader_decision_needed"]).lower()}
latest_owner = {summary["latest_owner"]}
trend = {summary["trend"]}
```

This summary reads timestamped autopilot records and reports the recent Software Open Claw duty trend.

## Recent Runs

| Run ID | Status | Blocking Tasks | Leader Decision | Owner |
| --- | --- | ---: | --- | --- |
{rows}

## Counts

```text
status_counts = {dict(status_counts)}
blocking_run_count = {len(blocking_runs)}
leader_decision_run_count = {len(leader_runs)}
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

    print("410HEALTH AUTOPILOT HISTORY SUMMARY")
    print(f"runs={len(runs)}")
    print(f"latest_run_id={summary['latest_run_id']}")
    print(f"latest_status={summary['latest_status']}")
    print(f"trend={summary['trend']}")
    print(f"report={REPORT_PATH}")
    print(f"summary={SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
