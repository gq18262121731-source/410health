# 410health Remote Branch Governance Policy

```text
phase = SE-3.5
mode = policy_only
result = ready_for_leader_review
```

## Current State

```text
remote_collaboration = enabled
remote_name = origin
remote_url = https://github.com/gq18262121731-source/410health.git
local_master = a5395c8
tracking = origin/master
historical_lobster_branches = local_only
```

`origin/master` now contains the local Software Open Claw mainline. The remote also has historical branches, including `main`, from earlier remote activity. This policy does not modify remote defaults or branch protection.

## main / master Relationship

```text
main = existing remote history branch, do not rewrite
master = current Software Open Claw 410health mainline
origin/master = remote mirror of local master
```

Recommended near-term policy:

```text
keep main unchanged
use master for current Software Open Claw line
do not merge main/master until leader approves a reconciliation plan
```

## Default Branch Recommendation

```text
recommended_default_branch = defer_decision
```

Do not change the GitHub default branch during this phase. First decide whether the organization wants:

```text
Option A: keep GitHub default as main and treat master as imported Software Open Claw line
Option B: switch GitHub default to master after reviewing remote main history
Option C: reconcile main and master into a new protected default branch
```

## Remote Branch Naming

Future remote collaboration branches should use:

```text
feature/<short-purpose>
fix/<short-purpose>
docs/<short-purpose>
software-open-claw/<workflow-purpose>
```

Examples:

```text
feature/daily-autopilot-dashboard
fix/frontend-check-regression
docs/operator-runbook
software-open-claw/410health-local-sync-001
```

## lobster/* Policy

```text
lobster/* = historical local repair branches
remote_push = prohibited by default
```

Historical `lobster/*` branches should stay local unless the leader requests a specific branch for audit or review. New remote-facing work should use `feature/*`, `fix/*`, `docs/*`, or `software-open-claw/*`.

## Push Rules

```text
direct_push_master = prohibited unless explicitly approved
direct_push_main = prohibited
force_push = prohibited
push_all_branches = prohibited
push_tags = prohibited unless release-approved
```

Allowed after approval:

```text
push feature/fix/docs/software-open-claw review branches
push master only for approved sync or release checkpoint
```

## PR / Merge Rules

```text
pull_request_required = recommended
leader_approval_required = true
pre_merge_checks_required = true
```

Minimum checks before merge:

```powershell
python scripts/run_410health_daily_autopilot.py
npm run check --prefix frontend/vue-dashboard
```

Required merge report fields:

```text
source_branch
target_branch
checks_passed
leader_approval_received
force_push_attempted = false
deployment_attempted = false
dependency_install_attempted = false
```

## Tag Strategy

```text
tag_creation = release-only
tag_push = leader approval required
recommended_format = vYYYY.MM.DD or software-open-claw-<milestone>
```

No tags should be created for routine daily operation or small repair branches.

## Rollback Strategy

Rollback order:

```text
1. use git revert for pushed commits
2. use prior local backup if repository state is corrupted
3. use remote branch history for recovery
```

Do not use remote history rewriting as a rollback mechanism.

## Boundary

```text
remote_branch_created = false
default_branch_changed = false
branch_protection_changed = false
tag_created = false
push_attempted = false
deployment_attempted = false
dependency_install_attempted = false
```
