# 410health Device Registration Flow Demo Directory Fix Report

## Summary

Phase SE-1.0B / Demo Directory Variable Name Fix is complete and waiting for leader review.

```text
branch = lobster/device-registration-flow-fix-demo-directory-001
target_failure = tests/test_device_registration_flow.py::test_demo_directory_strictly_matches_setup_account_layout
targeted_test = 1 passed
device_registration_flow = 17 passed, 1 failed
full_pytest = 94 passed, 1 failed
merge_to_master_attempted = false
git_push_attempted = false
deployment_attempted = false
```

## Diagnosis

The target failure was a stale test variable name issue, not a business logic defect.

Current demo persona contract:

```text
elder01_01 = 张三
elder01_02 = 李四
```

Evidence:

```text
setup.md lists elder01_01 as 张三 and elder01_02 as 李四.
backend/services/care_service.py uses DemoElderSeed names 张三 / 李四.
The test already assigned zhang_san and li_si variables, but assertions still referenced wang_xiuying / li_jianguo.
```

## Change Scope

Changed files:

```text
tests/test_device_registration_flow.py
```

Patch summary:

```text
Replaced stale assertion variables wang_xiuying / li_jianguo with zhang_san / li_si.
No CareService changes.
No DeviceService changes.
No device_api changes.
No active serial target logic changes.
No unbind_self seam changes.
```

## Verification

Targeted test:

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
merge_to_master_attempted = false
```

## Approval Request

This branch is ready for leader review. If approved, merge `lobster/device-registration-flow-fix-demo-directory-001` into `master`, rerun the targeted test, rerun `tests/test_device_registration_flow.py -q`, and rerun full pytest.
