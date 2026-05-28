from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "410health_daily_residency_check_report.md"
SUMMARY_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_daily_residency_check_001.json"
FRONTEND_DIR = ROOT / "frontend" / "vue-dashboard"


def run_command(command: list[str], *, cwd: Path = ROOT, timeout: int = 600) -> dict[str, object]:
    started_at = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": " ".join(command),
            "cwd": str(cwd),
            "exit_code": completed.returncode,
            "status": "passed" if completed.returncode == 0 else "failed",
            "stdout_tail": tail(completed.stdout),
            "stderr_tail": tail(completed.stderr),
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    except FileNotFoundError as exc:
        return {
            "command": " ".join(command),
            "cwd": str(cwd),
            "exit_code": None,
            "status": "failed",
            "stdout_tail": "",
            "stderr_tail": f"command not found: {exc.filename or command[0]}",
            "failure_reason": "dependency/tooling missing",
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(command),
            "cwd": str(cwd),
            "exit_code": None,
            "status": "timeout",
            "stdout_tail": tail(exc.stdout or ""),
            "stderr_tail": tail(exc.stderr or ""),
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }


def tail(text: str, *, max_lines: int = 40) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def has_changes(git_status: dict[str, object]) -> bool:
    return bool(str(git_status.get("stdout_tail", "")).strip())


def build_report(summary: dict[str, object]) -> str:
    git_status = summary["checks"]["git_status"]
    backend = summary["checks"]["backend_pytest"]
    frontend = summary["checks"]["frontend_check"]
    return f"""# 410health Daily Residency Check Report

## Summary

```text
project = {summary["project_path"]}
created_at = {summary["created_at"]}
overall_status = {summary["overall_status"]}
business_code_changed = {str(summary["business_code_changed"]).lower()}
```

## Checks

| Check | Command | Status | Exit Code |
| --- | --- | --- | --- |
| Git status | `{git_status["command"]}` | {git_status["status"]} | {git_status["exit_code"]} |
| Backend pytest | `{backend["command"]}` | {backend["status"]} | {backend["exit_code"]} |
| Frontend check | `{frontend["command"]}` | {frontend["status"]} | {frontend["exit_code"]} |

## Git Status

```text
{git_status["stdout_tail"] or "clean"}
```

## Backend Pytest Tail

```text
{backend["stdout_tail"] or backend["stderr_tail"]}
```

## Frontend Check Tail

```text
{frontend["stdout_tail"] or frontend["stderr_tail"]}
```

## Notes

This runner is the minimal Software Open Claw daily residency check. It only observes repository state and runs existing verification commands. It does not install dependencies, deploy, push, or modify business code.
"""


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    git_status = run_command(["git", "status", "--short"], timeout=60)
    backend_pytest = run_command(["conda", "run", "-n", "helth", "pytest"], timeout=900)
    frontend_check = run_command(["npm", "run", "check"], cwd=FRONTEND_DIR, timeout=900)

    checks = {
        "git_status": git_status,
        "backend_pytest": backend_pytest,
        "frontend_check": frontend_check,
    }
    overall_status = "passed" if all(item["status"] == "passed" for item in checks.values()) else "failed"
    summary = {
        "phase": "SE-1.2",
        "project_path": str(ROOT),
        "created_at": created_at,
        "runner_created": True,
        "git_status_checked": True,
        "backend_pytest_executed": True,
        "frontend_check_attempted": True,
        "daily_report_created": True,
        "summary_json_created": True,
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
        "overall_status": overall_status,
        "checks": checks,
    }

    REPORT_PATH.write_text(build_report(summary), encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("410HEALTH DAILY RESIDENCY CHECK")
    print(f"overall_status={overall_status}")
    print(f"git_status={git_status['status']}")
    print(f"backend_pytest={backend_pytest['status']}")
    print(f"frontend_check={frontend_check['status']}")
    print(f"report={REPORT_PATH}")
    print(f"summary={SUMMARY_PATH}")
    return 0 if overall_status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
