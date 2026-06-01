# 410health Git Remote / Push Readiness Plan

```text
phase = SE-3.3
mode = plan_only
result = ready_for_leader_review
```

## Current Git State

```text
current_branch = master
working_tree = clean
remote_configured = false
push_attempted = false
```

The repository is currently local-only. No `origin` remote is configured, and no push has been attempted.

## Recommended Remote Strategy

```text
remote_name = origin
remote_type = private Git repository
default_branch = master
protected_master = required
direct_push_master = prohibited
feature_branch_push = allowed_after_leader_approval
```

The first remote should be a private repository controlled by the leader or organization. `master` should be treated as protected even if the hosting provider does not enforce protection yet.

## Push Branch Strategy

```text
master:
  direct_push = prohibited
  allowed_action = push only after explicit leader approval and clean validation

lobster/*:
  direct_push = allowed only after leader approves remote collaboration
  purpose = review branches, repair branches, controlled experiments

tags:
  first_tag = optional, e.g. software-open-claw-alpha-410health-green
  push_tags = leader approval required
```

## Required Pre-Push Checks

Run before the first approved remote push:

```powershell
cd D:\Program\410health
git status
git log --oneline -n 5
python scripts/run_410health_daily_autopilot.py
npm run check --prefix frontend/vue-dashboard
```

Expected:

```text
git_status = clean
daily_autopilot = passed
frontend_check = passed
backend_pytest = 95 passed
blocking_task_count = 0
```

## Backup / Rollback Rule

Before adding the remote and first push:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$src = "D:\Program\410health"
$backup = "D:\Program\410health_backups\410health_pre_remote_push_$timestamp"
robocopy $src $backup /E /XD .git node_modules venv .venv __pycache__ dist build target
```

Rollback source:

```text
local git history
pre-remote-push filesystem backup
remote branch history after first push
```

## Approval Checklist

Leader approval is required for:

```text
1. Remote repository URL
2. Whether remote is private
3. Whether master may be pushed
4. Whether lobster/* branches may be pushed
5. Whether tags should be created
6. Whether remote branch protection is available
7. Whether first push should include all local branches or master only
```

Recommended first push:

```powershell
git remote add origin <leader-approved-private-repo-url>
git push -u origin master
```

Recommended deferred action:

```text
Do not push all historical lobster/* branches until leader confirms remote review policy.
```

## Boundary

```text
remote_added = false
push_attempted = false
dependency_install_attempted = false
deployment_attempted = false
business_code_changed = false
```
