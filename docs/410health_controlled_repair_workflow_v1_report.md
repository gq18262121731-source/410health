# SE-4.6: Controlled Repair Workflow v1

## Summary

```text
phase = SE-4.6
result = passed
```

`scripts/prepare_410health_controlled_repair.py` now supports controlled repair plans for:

```text
backend_fail
frontend_fail
dirty_workspace
warning
dependency_block
vite_chunk_size_warning
```

The helper remains plan-only:

```text
branch_created = false
business_code_changed = false
merge_attempted = false
push_attempted = false
```

## Validation

```text
python scripts/prepare_410health_controlled_repair.py --task frontend_fail = passed
repair_plan_created = true
leader_approval_required = true
```

## Boundary

```text
business_code_changed = false
deployment_attempted = false
dependency_install_attempted = false
git_push_attempted = false
```
