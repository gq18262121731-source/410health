# 410health Residency History Summary

## Executive Summary

```text
created_at = 2026-06-01T02:40:33.307096+00:00
run_count = 3
latest_status = passed
latest_backend = passed
latest_frontend = passed
latest_backend_result = 95 passed in 101.78s (0:01:41)
health_trend = improving
```

Software Open Claw now has a minimal health trend view for 410health. The latest residency check is passing end to end, and the historical sequence shows the front-end check moving from unavailable or failed into a passing state.

## Status Counts

```text
overall_status_counts = {'failed': 2, 'passed': 1}
frontend_status_counts = {'failed': 2, 'passed': 1}
warning_counts = {}
```

## Run History

| Created At | Overall | Backend | Frontend | Backend Result | Warnings |
| --- | --- | --- | --- | --- | --- |
| 2026-05-28T01:52:38.272501+00:00 | `failed` | `passed` | `failed` | 95 passed in 101.64s (0:01:41) | none |
| 2026-05-28T02:26:51.197689+00:00 | `failed` | `passed` | `failed` | 95 passed in 102.51s (0:01:42) | none |
| 2026-06-01T02:38:28.440816+00:00 | `passed` | `passed` | `passed` | 95 passed in 101.78s (0:01:41) | none |

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
