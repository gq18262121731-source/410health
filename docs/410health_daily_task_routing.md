# 410health Daily Task Routing

## Summary

```text
phase = SE-2.1
overall_status = passed
backend_status = passed
frontend_status = passed
task_count = 1
blocking_task_count = 1
recommended_next_owner = safety_officer_lobster
```

The Software Open Claw task router converts the latest daily check into owner-specific next actions.

## Routed Tasks

| Task | Owner | Priority | Reason | Leader Approval |
| --- | --- | --- | --- | --- |
| inspect_dirty_workspace | safety_officer_lobster | `high` | git_status_has_uncommitted_or_untracked_changes | no |

## Current Decision

```text
primary_action = Inspect changed files before authorizing any code task.
```

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```
