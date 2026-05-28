# 410health Daily Autopilot Report

## Summary

```text
phase = SE-2.2
autopilot_status = needs_attention
daily_ops_chain = passed
task_routing = passed
blocking_task_count = 1
recommended_next_owner = safety_officer_lobster
```

The daily autopilot ran the Software Open Claw operating chain and task router in one command.

## Routed Tasks

| Task | Owner | Priority | Reason |
| --- | --- | --- | --- |
| inspect_dirty_workspace | safety_officer_lobster | `high` | git_status_has_uncommitted_or_untracked_changes |
| track_vite_chunk_size_warning | workflow_engineer_lobster | `low` | vite_chunk_size_warning_only |

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```
