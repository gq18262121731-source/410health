# Software Open Claw Tool Registry

## Summary

```text
project = 410health
registry_scope = local residency tools
tool_count = 5
default_mode = observe_and_report
production_write_allowed = false
deployment_allowed = false
git_push_allowed = false
dependency_install_allowed = false
```

This registry lists the current tools available to the lobster employees for daily 410health residency work. These tools observe the repository, run existing checks, generate reports, and summarize trends. They do not deploy, push, install dependencies, or modify business code.

## Registered Tools

| Tool | Command | Purpose | Risk | Auto-run |
| --- | --- | --- | --- | --- |
| Daily Residency Check | `python scripts/run_410health_daily_residency_check.py` | Run `git status`, backend pytest, and frontend check. | medium | yes |
| Daily Ops Summary | `python scripts/build_410health_daily_ops_summary.py` | Convert latest check JSON into leader report and team-room note. | low | yes |
| Residency History Index | `python scripts/build_410health_residency_history_index.py` | Build trend index from daily check JSON files. | low | yes |
| Daily Ops Chain | `python scripts/run_410health_daily_ops_chain.py` | Run check, daily summary, and history index in one command. | medium | yes |
| Bundle Warning Triage | `python scripts/analyze_410health_frontend_bundle_warning.py` | Explain Vite chunk-size warning from built assets. | low | yes |

## Usage Rules

```text
allowed_without_leader_approval = observe, test, report, summarize
requires_leader_approval = code changes, dependency install, deploy, git push, destructive commands
default_owner = workflow_engineer_lobster
report_owner = product_manager_lobster
```

Recommended daily command:

```powershell
python scripts/run_410health_daily_ops_chain.py
```

Use bundle triage only when the daily report shows a frontend build-size warning:

```powershell
python scripts/analyze_410health_frontend_bundle_warning.py
```

## Tool Details

### Daily Residency Check

```text
tool_id = run_410health_daily_residency_check
command = python scripts/run_410health_daily_residency_check.py
mode = observe_and_verify
outputs =
  docs/410health_daily_residency_check_report.md
  evaluations/codebase_residency/410health_daily_residency_check_003.json
```

Runs existing verification commands and records pass/fail status. This tool may take a few minutes because it runs full backend pytest and frontend check.

### Daily Ops Summary

```text
tool_id = build_410health_daily_ops_summary
command = python scripts/build_410health_daily_ops_summary.py
mode = summarize
outputs =
  docs/410health_daily_ops_summary.md
  docs/410health_lobster_team_room.md
```

Turns machine output into a leader-readable daily status and a lobster team-room standup record.

### Residency History Index

```text
tool_id = build_410health_residency_history_index
command = python scripts/build_410health_residency_history_index.py
mode = trend_summary
outputs =
  evaluations/codebase_residency/410health_residency_history_index.json
  docs/410health_residency_history_summary.md
```

Summarizes recent daily check history and highlights health trend.

### Daily Ops Chain

```text
tool_id = run_410health_daily_ops_chain
command = python scripts/run_410health_daily_ops_chain.py
mode = orchestrate_existing_tools
outputs =
  evaluations/codebase_residency/410health_daily_ops_chain_001.json
```

Preferred daily entry point. Runs the daily residency check, ops summary, and history index in sequence.

### Bundle Warning Triage

```text
tool_id = analyze_410health_frontend_bundle_warning
command = python scripts/analyze_410health_frontend_bundle_warning.py
mode = diagnostic_report
outputs =
  docs/410health_frontend_bundle_warning_triage.md
  evaluations/codebase_residency/410health_frontend_bundle_warning_triage_001.json
```

Explains the current Vite chunk-size warning. The current known source is the isolated ECharts chunk, and it is non-blocking.

## Safety Boundary

These tools must not:

```text
install dependencies
deploy
push to remote
delete files
modify production configuration
merge branches
auto-fix code without approval
```

If any tool reports failure, the employee should generate a short triage note and wait for leader approval before modifying code.
