from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKLOG_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_autopilot_backlog.json"
TRIAGE_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_frontend_bundle_warning_triage_001.json"
REPORT_PATH = ROOT / "docs" / "410health_controlled_repair_plan.md"
PLAN_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_controlled_repair_plan_001.json"


TASK_CONFIG = {
    "vite_chunk_size_warning": {
        "recommended_branch": "lobster/optimize-vite-chunk-size-001",
        "risk": "medium",
        "allowed_scope": [
            "frontend/vue-dashboard/src/components/agent/AgentChartAttachment.vue",
            "frontend/vue-dashboard/src/components/*Chart*.vue",
            "frontend/vue-dashboard/vite.config.ts",
            "docs/410health_frontend_bundle_warning_triage.md",
            "evaluations/codebase_residency/410health_frontend_bundle_warning_triage_001.json"
        ],
        "prohibited_actions": [
            "Do not install dependencies.",
            "Do not deploy.",
            "Do not push.",
            "Do not auto-merge.",
            "Do not rewrite unrelated frontend routes.",
            "Do not change backend business code."
        ],
        "verification_commands": [
            "npm run check --prefix frontend/vue-dashboard",
            "python scripts/run_410health_daily_autopilot.py",
            "python scripts/analyze_410health_frontend_bundle_warning.py"
        ],
        "rollback": [
            "git checkout master",
            "git branch -D lobster/optimize-vite-chunk-size-001",
            "If merged later and regression appears, revert the merge commit with git revert <merge_commit> after leader approval."
        ]
    }
}


def _load_task(task_id: str) -> dict:
    backlog = json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))
    for item in backlog.get("items", []):
        if item.get("item_id") == task_id:
            return item
    raise SystemExit(f"Unknown backlog task: {task_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    args = parser.parse_args()

    if args.task not in TASK_CONFIG:
        raise SystemExit(f"No repair template for task: {args.task}")

    item = _load_task(args.task)
    triage = json.loads(TRIAGE_PATH.read_text(encoding="utf-8"))
    config = TASK_CONFIG[args.task]
    oversized = triage.get("oversized_js_chunks", [{}])[0]

    plan = {
        "phase": "SE-3.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "plan_only",
        "plan_created": True,
        "task_id": args.task,
        "risk": config["risk"],
        "problem_source": item.get("source"),
        "observed_chunk": oversized.get("name", item.get("observed_chunk")),
        "observed_size_kb": oversized.get("size_kb", item.get("observed_size_kb")),
        "current_impact": {
            "severity": item.get("severity"),
            "blocks_daily_autopilot": item.get("blocks_daily_autopilot", False),
            "leader_decision_needed_now": item.get("leader_decision_needed", False)
        },
        "recommended_branch": config["recommended_branch"],
        "leader_approval_required": True,
        "allowed_scope": config["allowed_scope"],
        "prohibited_actions": config["prohibited_actions"],
        "verification_commands": config["verification_commands"],
        "rollback_plan": config["rollback"],
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
        "branch_created": False,
        "merge_attempted": False
    }

    PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(
        f"""# 410health Controlled Repair Plan

## Summary

```text
phase = SE-3.0
mode = plan_only
plan_created = true
task_id = {plan["task_id"]}
risk = {plan["risk"]}
recommended_branch = {plan["recommended_branch"]}
leader_approval_required = true
```

## Problem

```text
source = {plan["problem_source"]}
observed_chunk = {plan["observed_chunk"]}
observed_size = {plan["observed_size_kb"]} KB
severity = {plan["current_impact"]["severity"]}
blocks_daily_autopilot = {str(plan["current_impact"]["blocks_daily_autopilot"]).lower()}
```

The current Vite chunk-size warning is non-blocking. This plan prepares a controlled optimization branch only if the leader approves.

## Allowed Scope

{chr(10).join(f"- `{item}`" for item in plan["allowed_scope"])}

## Prohibited Actions

{chr(10).join(f"- {item}" for item in plan["prohibited_actions"])}

## Verification Commands

{chr(10).join(f"- `{item}`" for item in plan["verification_commands"])}

## Rollback Plan

{chr(10).join(f"- `{item}`" for item in plan["rollback_plan"])}

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
branch_created = false
merge_attempted = false
```
""",
        encoding="utf-8",
    )

    print("410HEALTH CONTROLLED REPAIR PLAN")
    print("plan_created=true")
    print(f"task_id={plan['task_id']}")
    print(f"recommended_branch={plan['recommended_branch']}")
    print("leader_approval_required=true")
    print("business_code_changed=false")
    print("dependency_install_attempted=false")
    print("deployment_attempted=false")
    print("git_push_attempted=false")
    print(f"report={REPORT_PATH}")
    print(f"summary={PLAN_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
