# Software Open Claw Employee Operating Protocol

## Summary

```text
project = 410health
protocol_scope = daily residency operations
default_entrypoint = python scripts/run_410health_daily_ops_chain.py
default_mode = observe_and_report
business_code_write_allowed = false
auto_merge_allowed = false
deploy_allowed = false
git_push_allowed = false
```

This protocol defines who runs which Software Open Claw tools, when they run them, and how failures are escalated. It does not add new tools or permissions.

## Daily Operating Loop

```text
workflow_engineer_lobster
  -> run daily ops chain
  -> refresh reports and history
  -> post team-room status

product_manager_lobster
  -> read daily ops summary
  -> decide priority and owner
  -> prepare leader-facing note

qa_reviewer_lobster
  -> inspect failed checks or changed test evidence
  -> classify failure as environment, regression, expected warning, or unknown

safety_officer_lobster
  -> confirm no prohibited action occurred
  -> block deploy, push, dependency install, destructive commands, or auto-merge without approval
```

## Role Responsibilities

| Employee | Primary Responsibility | Default Tools | Escalates When |
| --- | --- | --- | --- |
| `workflow_engineer_lobster` | Keep the daily verification chain running. | `run_410health_daily_ops_chain.py` | Any required step fails. |
| `product_manager_lobster` | Convert results into priority and leadership language. | `build_410health_daily_ops_summary.py` | A failure needs product or release decision. |
| `qa_reviewer_lobster` | Review failed tests, evidence, and trend changes. | `run_410health_daily_residency_check.py`, history index | Backend/frontend checks fail or trend worsens. |
| `safety_officer_lobster` | Enforce no deploy, push, install, destructive action, or unapproved merge. | Tool registry and reports | Any tool or plan requests high-risk action. |

## When To Call Tools

### Normal Daily Start

```powershell
python scripts/run_410health_daily_ops_chain.py
```

Expected outputs:

```text
docs/410health_daily_residency_check_report.md
docs/410health_daily_ops_summary.md
docs/410health_lobster_team_room.md
docs/410health_residency_history_summary.md
evaluations/codebase_residency/410health_daily_ops_chain_001.json
```

### Non-blocking Bundle Warning

Use only when the daily report mentions the Vite chunk-size warning:

```powershell
python scripts/analyze_410health_frontend_bundle_warning.py
```

Current known state:

```text
source = echarts charting dependency
severity = non_blocking
action_now = no urgent code change
```

## Failure Escalation Rules

| Situation | Classification | Immediate Action | Needs Leader Approval |
| --- | --- | --- | --- |
| Backend pytest fails | regression_or_test_failure | Stop and write triage note. | yes, before code changes |
| Frontend check fails | frontend_regression_or_tooling_issue | Record failure and classify. | yes, before code changes |
| Git status dirty before run | workspace_not_clean | Stop and inspect changed files. | maybe |
| Vite chunk-size warning only | expected_non_blocking_warning | Track in backlog. | no |
| Dependency missing | environment_blocked | Report missing tooling; do not install. | yes, before install |
| Deploy/push requested | high_risk_action | Block by default. | yes |
| Code change requested | controlled_fix_needed | Create branch and plan minimal fix. | yes, before merge |

## Approval Boundary

Allowed without leader approval:

```text
observe
run existing tests/checks
generate reports
summarize history
diagnose non-blocking warnings
```

Requires leader approval:

```text
business code changes
frontend code changes
dependency installation
deployment
git push
branch merge
destructive filesystem operation
production configuration changes
```

## End-of-Day Handoff

Each day, the team-room record should answer:

```text
1. Is git status clean?
2. Did backend pytest pass?
3. Did frontend check pass?
4. Are there warnings?
5. Is any action blocked on leader approval?
6. Who owns the next step?
```

Current default owner:

```text
workflow_engineer_lobster = daily tool execution
product_manager_lobster = leader-facing summary
qa_reviewer_lobster = failed check review
safety_officer_lobster = approval boundary review
```
