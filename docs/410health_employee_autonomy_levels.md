# SE-5.6: Employee Autonomy Levels

```text
phase = SE-5.6
result = passed
default_mode = controlled_autonomy
```

## Levels

| Level | Scope | Default Status |
| --- | --- | --- |
| L0 observe/report | Run autopilot, reports, team room, triage | enabled |
| L1 propose | Generate repair plans and patch drafts | enabled |
| L2 edit_low_risk | Edit docs/tests after explicit approval | conditional |
| L3 edit_product_code | Edit backend/frontend after task-specific approval | disabled |
| L4 deploy/merge/push-master | Deploy, merge, push protected branches | leader-only |

## Employee Defaults

```text
workflow_engineer_lobster = L1, eligible_for_L2_docs_tests_after_approval
qa_reviewer_lobster = L1, eligible_for_L2_tests_after_approval
product_manager_lobster = L0
safety_officer_lobster = approval_gate
```

## Hard Stops

```text
auto_deploy = forbidden
auto_merge = forbidden
auto_push_master = forbidden
auto_dependency_install = forbidden
business_code_edit_without_approval = forbidden
```
