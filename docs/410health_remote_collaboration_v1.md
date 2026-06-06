# SE-4.7: Remote Collaboration v1

## Summary

```text
phase = SE-4.7
result = partially_verified_pr_blocked
```

## Branch Model

```text
master = Software Open Claw mainline
main = existing remote history branch, unchanged
feature/* = feature work
fix/* = repair work
docs/* = documentation work
software-open-claw/* = workflow/system integration work
lobster/* = historical local branches, not pushed by default
```

## Standard Workflow

```powershell
git checkout master
git pull --ff-only origin master
git checkout -b fix/<short-task>
python scripts/run_410health_daily_autopilot.py
npm run check --prefix frontend/vue-dashboard
git push -u origin fix/<short-task>
```

Then a collaborator account creates a PR and merges after review.

## Verified

```text
feature_branch_push = passed
remote_branch = origin/docs/software-open-claw-remote-workflow-trial
business_code_changed = false
```

## Blocked

```text
PR_created = false
reason = GitHub collaborator permission unavailable
gh_cli_available = false
merged_after_approval = false
remote_branch_deleted_after_merge = false
```

## Rules

```text
force_push = prohibited
direct_push_main = prohibited
direct_push_master = prohibited unless explicitly approved
push_all_branches = prohibited
push_tags = release approval required
```

## Boundary

```text
deployment_attempted = false
dependency_install_attempted = false
main_changed = false
master_history_rewritten = false
lobster_branches_pushed = false
```
