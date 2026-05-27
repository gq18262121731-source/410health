# 410health Device Registration Flow Demo Directory Fix Merge Report

## Summary

Phase SE-1.0B-C / Approved Merge for Demo Directory Variable Name Fix is complete.

```text
source_branch = lobster/device-registration-flow-fix-demo-directory-001
target_branch = master
merge_executed = true
merge_commit = 4ee3b0f
targeted_test = 1 passed
device_registration_flow = 17 passed, 1 failed
full_pytest = 94 passed, 1 failed
new_failure_detected = false
```

## Approved Change

This merge aligns stale test assertion variables with the current demo persona contract.

Current demo persona contract:

```text
elder01_01 = 张三
elder01_02 = 李四
```

Merged behavior:

```text
wang_xiuying assertions -> zhang_san assertions
li_jianguo assertions -> li_si assertions
```

Changed files merged:

```text
tests/test_device_registration_flow.py
docs/410health_device_registration_flow_demo_directory_fix_report.md
evaluations/codebase_residency/410health_device_registration_flow_demo_directory_fix_001.json
```

## Master Verification

Targeted verification:

```powershell
conda run -n helth pytest tests/test_device_registration_flow.py::test_demo_directory_strictly_matches_setup_account_layout -q
```

Result:

```text
1 passed
```

Device registration flow regression:

```powershell
conda run -n helth pytest tests/test_device_registration_flow.py -q
```

Result:

```text
17 passed, 1 failed
```

Full regression:

```powershell
conda run -n helth pytest
```

Result:

```text
94 passed, 1 failed
```

Remaining known failure:

```text
tests/test_device_registration_flow.py::test_unbind_self_prioritizes_active_serial_target
```

## Boundary Confirmation

```text
care_service_touched = false
device_service_touched = false
device_api_touched = false
active_serial_target_logic_touched = false
unbind_self_seam_touched = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```

## Result

The demo directory variable name fix has been merged into `master` under leader approval. Master is verified at `94 passed, 1 failed`, with no new failure detected.
