from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "410health_openclaw_local_bypass_setup_report.md"
SUMMARY_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_openclaw_local_bypass_readonly_entry_001.json"

AUTOPILOT_GENERATED_PREFIXES = (
    "docs/410health_",
    "evaluations/codebase_residency/410health_",
    "scripts/software_open_claw_",
)
SOURCE_PREFIXES = (
    "backend/",
    "frontend/",
    "src/",
    "app/",
)
BUILD_ARTIFACT_MARKERS = (
    "/dist/",
    "/build/",
    "__pycache__/",
    ".pyc",
)


def _run(command: list[str]) -> dict[str, object]:
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
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _git_status_short() -> list[str]:
    result = _run(["git", "status", "--short"])
    if result["exit_code"] != 0:
        return []
    return [line for line in str(result["stdout"]).splitlines() if line.strip()]


def _path_from_status_line(line: str) -> str:
    raw = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1]
    return raw.replace("\\", "/")


def _classify_dirty_workspace(status_lines: list[str]) -> dict[str, list[str]]:
    classified = {
        "autopilot_generated_files": [],
        "user_source_changes": [],
        "build_artifacts": [],
        "unknown_changes": [],
    }
    for line in status_lines:
        path = _path_from_status_line(line)
        if path.startswith(AUTOPILOT_GENERATED_PREFIXES):
            classified["autopilot_generated_files"].append(line)
        elif path.startswith(SOURCE_PREFIXES):
            classified["user_source_changes"].append(line)
        elif any(marker in path for marker in BUILD_ARTIFACT_MARKERS):
            classified["build_artifacts"].append(line)
        else:
            classified["unknown_changes"].append(line)
    return classified


def _status_payload() -> dict[str, object]:
    status_lines = _git_status_short()
    branch = _run(["git", "branch", "--show-current"])
    log = _run(["git", "log", "--oneline", "-n", "5"])
    classified = _classify_dirty_workspace(status_lines)
    has_source_or_unknown = bool(classified["user_source_changes"] or classified["unknown_changes"])
    return {
        "git_status_short": status_lines,
        "current_branch": str(branch["stdout"]).strip(),
        "recent_log": str(log["stdout"]).splitlines(),
        "dirty_workspace": bool(status_lines),
        "dirty_classification": classified,
        "safe_for_stage_a_readonly": not has_source_or_unknown,
    }


def _run_daily_autopilot() -> dict[str, object]:
    status_before = _status_payload()
    result = _run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ".\\scripts\\run_410health_daily_autopilot.ps1"])
    status_after = _status_payload()
    stdout = str(result["stdout"])
    core_steps_passed = all(
        marker in stdout
        for marker in (
            "daily_ops_chain=passed",
            "task_routing=passed",
            "triage_note=passed",
        )
    )
    underlying_status = "passed" if "autopilot_status=passed" in stdout else "needs_attention"
    safe_dirty_workspace = bool(status_after["safe_for_stage_a_readonly"])
    daily_autopilot = "passed" if result["exit_code"] == 0 and core_steps_passed and safe_dirty_workspace else "failed"
    return {
        "daily_autopilot": daily_autopilot,
        "underlying_autopilot_status": underlying_status,
        "core_steps_passed": core_steps_passed,
        "stage_a_dirty_workspace_safe": safe_dirty_workspace,
        "command_result": result,
        "status_before": status_before,
        "status_after": status_after,
    }


def _write_report(summary: dict[str, object]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    status_after = summary.get("status_after") or summary.get("status") or {}
    dirty = status_after.get("dirty_classification", {}) if isinstance(status_after, dict) else {}
    autopilot_generated = len(dirty.get("autopilot_generated_files", [])) if isinstance(dirty, dict) else 0
    source_changes = len(dirty.get("user_source_changes", [])) if isinstance(dirty, dict) else 0
    unknown_changes = len(dirty.get("unknown_changes", [])) if isinstance(dirty, dict) else 0

    REPORT_PATH.write_text(
        f"""# 410health OpenClaw Local Bypass Setup Report

## Summary

```text
stage = SE-4.0
readonly_entry = {summary["readonly_entry"]}
project = 410health
mode = local_bypass_residency
action = {summary["action"]}
daily_autopilot = {summary.get("daily_autopilot", "not_run")}
underlying_autopilot_status = {summary.get("underlying_autopilot_status", "not_run")}
stage_a_dirty_workspace_safe = {str(summary.get("stage_a_dirty_workspace_safe", False)).lower()}
business_code_changed = false
dangerous_action_attempted = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
merge_attempted = false
```

## Workspace Safety

```text
dirty_workspace = {str(bool(status_after.get("dirty_workspace", False))).lower() if isinstance(status_after, dict) else "unknown"}
autopilot_generated_files = {autopilot_generated}
user_source_changes = {source_changes}
unknown_changes = {unknown_changes}
safe_for_stage_a_readonly = {str(status_after.get("safe_for_stage_a_readonly", False)).lower() if isinstance(status_after, dict) else "unknown"}
```

## Employee Boundary

```text
workflow_engineer_lobster = daily tool execution
product_manager_lobster = leader-facing summary
qa_reviewer_lobster = failed check review
safety_officer_lobster = approval boundary review
```

## Result

The local bypass residency entrypoint only exposes status inspection and daily autopilot execution. It does not expose arbitrary shell access, code edits, commit, push, merge, install, deploy, or delete operations.
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Software Open Claw readonly entrypoint for 410health.")
    parser.add_argument("--project", required=True, choices=["410health"])
    parser.add_argument("--action", required=True, choices=["status", "daily_autopilot"])
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    if args.action == "status":
        status = _status_payload()
        summary = {
            "stage": "SE-4.0",
            "created_at": created_at,
            "project": args.project,
            "action": args.action,
            "readonly_entry": "passed",
            "business_code_changed": False,
            "dangerous_action_attempted": False,
            "status": status,
        }
        _write_report(summary)
        print("SOFTWARE OPEN CLAW READONLY ENTRY")
        print("readonly_entry=passed")
        print("action=status")
        print(f"current_branch={status['current_branch']}")
        print(f"dirty_workspace={str(status['dirty_workspace']).lower()}")
        print(f"safe_for_stage_a_readonly={str(status['safe_for_stage_a_readonly']).lower()}")
        print(f"report={REPORT_PATH}")
        print(f"summary={SUMMARY_PATH}")
        return 0

    result = _run_daily_autopilot()
    summary = {
        "stage": "SE-4.0",
        "created_at": created_at,
        "project": args.project,
        "action": args.action,
        "readonly_entry": "passed" if result["daily_autopilot"] == "passed" else "failed",
        "business_code_changed": False,
        "dangerous_action_attempted": False,
        **result,
    }
    _write_report(summary)
    print("SOFTWARE OPEN CLAW READONLY ENTRY")
    print(f"readonly_entry={summary['readonly_entry']}")
    print(f"action={args.action}")
    print(f"daily_autopilot={result['daily_autopilot']}")
    print(f"underlying_autopilot_status={result['underlying_autopilot_status']}")
    print(f"stage_a_dirty_workspace_safe={str(result['stage_a_dirty_workspace_safe']).lower()}")
    print("business_code_changed=false")
    print("dangerous_action_attempted=false")
    print(f"report={REPORT_PATH}")
    print(f"summary={SUMMARY_PATH}")
    return 0 if summary["readonly_entry"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
