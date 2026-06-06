# 410health Autopilot Triage Note

## Summary

```text
phase = SE-2.5
triage_status = action_required
leader_decision_needed = false
blocking_task_count = 1
approval_task_count = 0
recommended_next_owner = safety_officer_lobster
```

Autopilot detected blocking work that needs triage.

## Routed Tasks

| Task | Owner | Priority | Reason | Leader Approval |
| --- | --- | --- | --- | --- |
| inspect_dirty_workspace | safety_officer_lobster | `high` | git_status_has_uncommitted_or_untracked_changes | no |

## Recommended Next Action

```text
Inspect changed files before authorizing any code task.
```

## Prohibited Actions

```text
Do not modify business code without approval.
Do not install dependencies without approval.
Do not deploy.
Do not push to remote.
Do not merge branches without approval.
```

## Boundary

```text
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```
