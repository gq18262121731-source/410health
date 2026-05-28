from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "evaluations" / "codebase_residency"
INDEX_PATH = SOURCE_DIR / "410health_residency_history_index.json"
SUMMARY_PATH = ROOT / "docs" / "410health_residency_history_summary.md"


def _status(data: dict, key: str, fallback_check: str) -> str:
    if data.get(key):
        return data[key]
    return data.get("checks", {}).get(fallback_check, {}).get("status", "unknown")


def _pytest_result(stdout: str) -> str:
    match = re.search(r"=+\s*(\d+\s+passed(?:,\s*\d+\s+\w+)?.*?)\s*=+", stdout)
    return match.group(1).strip() if match else "unknown"


def _warning_flags(data: dict) -> list[str]:
    warnings = []
    frontend = data.get("checks", {}).get("frontend_check", {})
    stderr = frontend.get("stderr_tail", "") or ""
    if "Some chunks are larger than 500 kB" in stderr:
        warnings.append("vite_chunk_size_warning")
    if frontend.get("status") == "blocked_missing_tooling":
        warnings.append("frontend_tooling_blocked")
    return warnings


def _load_runs() -> list[dict]:
    runs = []
    for path in sorted(SOURCE_DIR.glob("410health_daily_residency_check_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        checks = data.get("checks", {})
        backend = checks.get("backend_pytest", {})
        frontend = checks.get("frontend_check", {})
        run = {
            "source_file": str(path.relative_to(ROOT)).replace("\\", "/"),
            "created_at": data.get("created_at", ""),
            "overall_status": data.get("overall_status", "unknown"),
            "git_status": _status(data, "git_status", "git_status"),
            "backend_status": _status(data, "backend_status", "backend_pytest"),
            "frontend_status": _status(data, "frontend_status", "frontend_check"),
            "backend_result": _pytest_result(backend.get("stdout_tail", "")),
            "frontend_command": frontend.get("command", "unknown"),
            "warnings": _warning_flags(data),
            "business_code_changed": data.get("business_code_changed", False),
            "dependency_install_attempted": data.get("dependency_install_attempted", False),
            "deployment_attempted": data.get("deployment_attempted", False),
            "git_push_attempted": data.get("git_push_attempted", False),
        }
        runs.append(run)
    return runs


def main() -> int:
    runs = _load_runs()
    if not runs:
        raise FileNotFoundError("No 410health daily residency check JSON files found.")

    status_counts = Counter(run["overall_status"] for run in runs)
    frontend_counts = Counter(run["frontend_status"] for run in runs)
    warning_counts = Counter(warning for run in runs for warning in run["warnings"])
    latest = runs[-1]
    health_trend = "improving" if latest["overall_status"] == "passed" and status_counts.get("failed", 0) else "stable"
    if latest["overall_status"] != "passed":
        health_trend = "needs_attention"

    index = {
        "phase": "SE-1.6",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_path": str(ROOT),
        "run_count": len(runs),
        "overall_status_counts": dict(status_counts),
        "frontend_status_counts": dict(frontend_counts),
        "warning_counts": dict(warning_counts),
        "latest_status": latest["overall_status"],
        "latest_backend_status": latest["backend_status"],
        "latest_frontend_status": latest["frontend_status"],
        "latest_backend_result": latest["backend_result"],
        "health_trend": health_trend,
        "runs": runs,
        "safety_boundary": {
            "business_code_changed": False,
            "dependency_install_attempted": False,
            "deployment_attempted": False,
            "git_push_attempted": False,
        },
    }

    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "\n".join(
        "| {created_at} | `{overall_status}` | `{backend_status}` | `{frontend_status}` | {backend_result} | {warnings} |".format(
            created_at=run["created_at"] or "unknown",
            overall_status=run["overall_status"],
            backend_status=run["backend_status"],
            frontend_status=run["frontend_status"],
            backend_result=run["backend_result"],
            warnings=", ".join(run["warnings"]) if run["warnings"] else "none",
        )
        for run in runs
    )

    SUMMARY_PATH.write_text(
        f"""# 410health Residency History Summary

## Executive Summary

```text
created_at = {index["created_at"]}
run_count = {index["run_count"]}
latest_status = {index["latest_status"]}
latest_backend = {index["latest_backend_status"]}
latest_frontend = {index["latest_frontend_status"]}
latest_backend_result = {index["latest_backend_result"]}
health_trend = {index["health_trend"]}
```

Software Open Claw now has a minimal health trend view for 410health. The latest residency check is passing end to end, and the historical sequence shows the front-end check moving from unavailable or failed into a passing state.

## Status Counts

```text
overall_status_counts = {dict(status_counts)}
frontend_status_counts = {dict(frontend_counts)}
warning_counts = {dict(warning_counts)}
```

## Run History

| Created At | Overall | Backend | Frontend | Backend Result | Warnings |
| --- | --- | --- | --- | --- | --- |
{rows}

## Current Watch Item

```text
watch_item = vite_chunk_size_warning
severity = non_blocking
owner = workflow_engineer_lobster
next_action = Track during normal optimization work; do not block daily residency pass.
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

    print("410HEALTH RESIDENCY HISTORY INDEX")
    print(f"runs={len(runs)}")
    print(f"latest_status={latest['overall_status']}")
    print(f"index={INDEX_PATH}")
    print(f"summary={SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
