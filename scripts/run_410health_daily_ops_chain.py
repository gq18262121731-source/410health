from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "evaluations" / "codebase_residency" / "410health_daily_ops_chain_001.json"


STEPS = [
    {
        "name": "daily_residency_check",
        "command": [sys.executable, "scripts/run_410health_daily_residency_check.py"],
        "required": True,
    },
    {
        "name": "daily_ops_summary",
        "command": [sys.executable, "scripts/build_410health_daily_ops_summary.py"],
        "required": True,
    },
    {
        "name": "residency_history_index",
        "command": [sys.executable, "scripts/build_410health_residency_history_index.py"],
        "required": True,
    },
]


def _tail(text: str, max_lines: int = 30) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-max_lines:])


def _run_step(step: dict[str, object]) -> dict[str, object]:
    started_at = datetime.now(timezone.utc)
    completed = subprocess.run(
        step["command"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "name": step["name"],
        "command": " ".join(step["command"]),
        "required": step["required"],
        "exit_code": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    results = [_run_step(step) for step in STEPS]
    required_failed = [result for result in results if result["required"] and result["status"] != "passed"]
    overall_status = "passed" if not required_failed else "failed"

    summary = {
        "phase": "SE-1.7",
        "created_at": created_at,
        "project_path": str(ROOT),
        "overall_status": overall_status,
        "steps_total": len(results),
        "steps_passed": sum(1 for result in results if result["status"] == "passed"),
        "steps_failed": sum(1 for result in results if result["status"] != "passed"),
        "business_code_changed": False,
        "dependency_install_attempted": False,
        "deployment_attempted": False,
        "git_push_attempted": False,
        "steps": results,
        "artifacts": {
            "daily_check_report": "docs/410health_daily_residency_check_report.md",
            "daily_check_json": "evaluations/codebase_residency/410health_daily_residency_check_003.json",
            "daily_ops_summary": "docs/410health_daily_ops_summary.md",
            "lobster_team_room": "docs/410health_lobster_team_room.md",
            "history_index": "evaluations/codebase_residency/410health_residency_history_index.json",
            "history_summary": "docs/410health_residency_history_summary.md",
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("410HEALTH DAILY OPS CHAIN")
    for result in results:
        print(f"{result['name']}={result['status']}")
    print(f"overall_status={overall_status}")
    print(f"summary={SUMMARY_PATH}")
    return 0 if overall_status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
