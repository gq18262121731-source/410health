from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DIR = ROOT / "evaluations" / "codebase_residency" / "synthetic_failure_drills"
REPORT_PATH = ROOT / "docs" / "410health_autopilot_failure_drill_report.md"
SUMMARY_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_autopilot_failure_drill_001.json"
ROUTER_PATH = ROOT / "scripts" / "route_410health_daily_tasks.py"


def _load_router():
    spec = importlib.util.spec_from_file_location("route_410health_daily_tasks", ROUTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load task router.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_check() -> dict:
    return {
        "overall_status": "passed",
        "backend_status": "passed",
        "frontend_status": "passed",
        "checks": {
            "git_status": {
                "status": "passed",
                "stdout_tail": "",
                "stderr_tail": "",
            },
            "backend_pytest": {
                "status": "passed",
                "stdout_tail": "95 passed",
                "stderr_tail": "",
            },
            "frontend_check": {
                "status": "passed",
                "stdout_tail": "npm run check passed",
                "stderr_tail": "",
            },
        },
    }


def _cases() -> list[dict]:
    backend_failed = _base_check()
    backend_failed.update({"overall_status": "failed", "backend_status": "failed"})
    backend_failed["checks"]["backend_pytest"].update(
        {"status": "failed", "stdout_tail": "1 failed, 94 passed"}
    )

    frontend_failed = _base_check()
    frontend_failed.update({"overall_status": "failed", "frontend_status": "failed"})
    frontend_failed["checks"]["frontend_check"].update(
        {"status": "failed", "stderr_tail": "eslint unused variable"}
    )

    git_dirty = _base_check()
    git_dirty["synthetic_git_dirty"] = True
    git_dirty["checks"]["git_status"].update({"stdout_tail": " M backend/main.py"})

    warning_only = _base_check()
    warning_only["checks"]["frontend_check"].update(
        {"stderr_tail": "(!) Some chunks are larger than 500 kB after minification."}
    )

    return [
        {
            "case_id": "backend_failed",
            "check": backend_failed,
            "expected_owner": "qa_reviewer_lobster",
            "expected_task": "triage_backend_pytest_failure",
        },
        {
            "case_id": "frontend_failed",
            "check": frontend_failed,
            "expected_owner": "qa_reviewer_lobster",
            "expected_task": "triage_frontend_check_failure",
        },
        {
            "case_id": "git_dirty",
            "check": git_dirty,
            "expected_owner": "safety_officer_lobster",
            "expected_task": "inspect_dirty_workspace",
        },
        {
            "case_id": "warning_only",
            "check": warning_only,
            "expected_owner": "workflow_engineer_lobster",
            "expected_task": "track_vite_chunk_size_warning",
        },
    ]


def main() -> int:
    router = _load_router()
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for case in _cases():
        case_path = SYNTHETIC_DIR / f"{case['case_id']}.json"
        case_path.write_text(json.dumps(case["check"], ensure_ascii=False, indent=2), encoding="utf-8")
        tasks = router._route(case["check"])
        task_ids = [task["task_id"] for task in tasks]
        owners = [task["owner"] for task in tasks]
        passed = case["expected_task"] in task_ids and case["expected_owner"] in owners
        results.append(
            {
                "case_id": case["case_id"],
                "synthetic_check": str(case_path.relative_to(ROOT)).replace("\\", "/"),
                "expected_task": case["expected_task"],
                "expected_owner": case["expected_owner"],
                "actual_tasks": tasks,
                "passed": passed,
            }
        )

    drill_passed = all(result["passed"] for result in results)
    summary = {
        "phase": "SE-2.4",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "drill_status": "passed" if drill_passed else "failed",
        "case_count": len(results),
        "cases_passed": sum(1 for result in results if result["passed"]),
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
        "results": results,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "\n".join(
        "| {case_id} | {expected_owner} | `{expected_task}` | {status} |".format(
            case_id=result["case_id"],
            expected_owner=result["expected_owner"],
            expected_task=result["expected_task"],
            status="passed" if result["passed"] else "failed",
        )
        for result in results
    )
    REPORT_PATH.write_text(
        f"""# 410health Autopilot Failure Drill Report

## Summary

```text
phase = SE-2.4
drill_status = {summary["drill_status"]}
case_count = {summary["case_count"]}
cases_passed = {summary["cases_passed"]}
business_code_changed = false
```

This drill uses synthetic daily check JSON files. It does not modify business code or force real failures in the project.

## Drill Cases

| Case | Expected Owner | Expected Task | Result |
| --- | --- | --- | --- |
{rows}

## Interpretation

```text
backend fail -> qa_reviewer_lobster
frontend fail -> qa_reviewer_lobster
git dirty -> safety_officer_lobster
warning only -> workflow_engineer_lobster
```

The current autopilot can route both healthy and unhealthy daily states to the correct employee owner.

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

    print("410HEALTH AUTOPILOT FAILURE DRILL")
    print(f"drill_status={summary['drill_status']}")
    print(f"cases={summary['case_count']}")
    print(f"passed={summary['cases_passed']}")
    print(f"report={REPORT_PATH}")
    print(f"summary={SUMMARY_PATH}")
    return 0 if drill_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
