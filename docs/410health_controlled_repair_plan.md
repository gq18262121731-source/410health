# 410health Controlled Repair Plan

## Summary

```text
phase = SE-3.0
mode = plan_only
plan_created = true
task_id = vite_chunk_size_warning
risk = medium
recommended_branch = lobster/optimize-vite-chunk-size-001
leader_approval_required = true
```

## Problem

```text
source = echarts charting dependency
observed_chunk = echarts-uvSR9kx1.js
observed_size = 803.9 KB
severity = non_blocking
blocks_daily_autopilot = false
```

The current Vite chunk-size warning is non-blocking. This plan prepares a controlled optimization branch only if the leader approves.

## Allowed Scope

- `frontend/vue-dashboard/src/components/agent/AgentChartAttachment.vue`
- `frontend/vue-dashboard/src/components/*Chart*.vue`
- `frontend/vue-dashboard/vite.config.ts`
- `docs/410health_frontend_bundle_warning_triage.md`
- `evaluations/codebase_residency/410health_frontend_bundle_warning_triage_001.json`

## Prohibited Actions

- Do not install dependencies.
- Do not deploy.
- Do not push.
- Do not auto-merge.
- Do not rewrite unrelated frontend routes.
- Do not change backend business code.

## Verification Commands

- `npm run check --prefix frontend/vue-dashboard`
- `python scripts/run_410health_daily_autopilot.py`
- `python scripts/analyze_410health_frontend_bundle_warning.py`

## Rollback Plan

- `git checkout master`
- `git branch -D lobster/optimize-vite-chunk-size-001`
- `If merged later and regression appears, revert the merge commit with git revert <merge_commit> after leader approval.`

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
branch_created = false
merge_attempted = false
```
