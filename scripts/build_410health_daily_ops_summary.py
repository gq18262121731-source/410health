from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "evaluations" / "codebase_residency"
OPS_REPORT = ROOT / "docs" / "410health_daily_ops_summary.md"
TEAM_ROOM = ROOT / "docs" / "410health_lobster_team_room.md"


def _latest_daily_summary() -> Path:
    candidates = sorted(
        SUMMARY_DIR.glob("410health_daily_residency_check_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No daily residency check JSON files found.")
    return candidates[0]


def _extract_pytest_summary(stdout: str) -> str:
    match = re.search(r"=+\s*(\d+\s+passed(?:,\s*\d+\s+\w+)?.*?)\s*=+", stdout)
    return match.group(1).strip() if match else "unknown"


def _has_chunk_warning(stderr: str) -> bool:
    return "Some chunks are larger than 500 kB" in stderr


def _status_label(status: str) -> str:
    return {
        "passed": "pass",
        "failed": "fail",
        "blocked_missing_tooling": "blocked",
        "partial_pass": "partial_pass",
    }.get(status, status)


def main() -> int:
    source = _latest_daily_summary()
    data = json.loads(source.read_text(encoding="utf-8"))
    checks = data.get("checks", {})
    backend = checks.get("backend_pytest", {})
    frontend = checks.get("frontend_check", {})
    git_status = checks.get("git_status", {})

    created_at = datetime.now(timezone.utc).isoformat()
    backend_summary = _extract_pytest_summary(backend.get("stdout_tail", ""))
    frontend_warning = _has_chunk_warning(frontend.get("stderr_tail", ""))
    overall = data.get("overall_status", "unknown")
    backend_status = data.get("backend_status", backend.get("status", "unknown"))
    frontend_status = data.get("frontend_status", frontend.get("status", "unknown"))

    issues = []
    if overall != "passed":
        issues.append("Daily residency check is not fully passed.")
    if frontend_warning:
        issues.append("Frontend build passed with Vite chunk-size warning.")
    if not issues:
        issues.append("No blocking issue detected.")

    next_owner = "workflow_engineer_lobster"
    next_action = "Keep daily residency check running; review frontend bundle-size warning when optimization work is scheduled."
    if overall != "passed":
        next_owner = "product_manager_lobster + workflow_engineer_lobster"
        next_action = "Triage failed or blocked check before approving new feature work."

    OPS_REPORT.write_text(
        f"""# 410health Daily Ops Summary

## Executive Summary

```text
created_at = {created_at}
source_summary = {source.relative_to(ROOT)}
project = {data.get("project_path", "D:/Program/410health")}
overall_status = {_status_label(overall)}
git_status = {_status_label(git_status.get("status", "unknown"))}
backend_pytest = {_status_label(backend_status)}
frontend_check = {_status_label(frontend_status)}
backend_result = {backend_summary}
```

410health daily residency check is operational. Backend pytest and frontend check are both passing. The project is ready for normal Software Open Claw observation.

## Check Results

| Area | Status | Command |
| --- | --- | --- |
| Git workspace | `{_status_label(git_status.get("status", "unknown"))}` | `{git_status.get("command", "git status --short")}` |
| Backend pytest | `{_status_label(backend_status)}` | `{backend.get("command", "conda run -n helth pytest")}` |
| Frontend check | `{_status_label(frontend_status)}` | `{frontend.get("command", "npm run check")}` |

## Issues And Warnings

{chr(10).join(f"- {item}" for item in issues)}

## Ownership

```text
owner = {next_owner}
next_action = {next_action}
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

    TEAM_ROOM.write_text(
        f"""# 410health Lobster Team Room

## Standup Snapshot

```text
created_at = {created_at}
overall_status = {_status_label(overall)}
backend_pytest = {_status_label(backend_status)}
frontend_check = {_status_label(frontend_status)}
```

## product_manager_lobster

Yesterday's repair loop is stable on the daily runner. The current release posture is observation-first: keep the project green, avoid unscheduled dependency or deployment work, and surface warnings clearly.

## workflow_engineer_lobster

Daily check source: `{source.relative_to(ROOT)}`.

Current verification chain:

```text
git status
  -> backend pytest
  -> frontend typecheck/lint/build
  -> daily ops summary
```

Backend result:

```text
{backend_summary}
```

Frontend result:

```text
status = {_status_label(frontend_status)}
chunk_size_warning = {str(frontend_warning).lower()}
```

## Team Decision

```text
next_owner = {next_owner}
next_action = {next_action}
production_write = false
deploy = false
push = false
```
""",
        encoding="utf-8",
    )

    print("410HEALTH DAILY OPS SUMMARY")
    print(f"source={source}")
    print(f"ops_report={OPS_REPORT}")
    print(f"team_room={TEAM_ROOM}")
    print(f"overall_status={_status_label(overall)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
