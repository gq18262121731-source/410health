# 410health Device Registration Flow Unbind Self Seam Fix Report

## Summary

Phase SE-1.0C / `unbind_device_self` `get_care_service` seam fix is complete and waiting for leader review.

```text
branch = lobster/device-registration-flow-fix-unbind-self-seam-001
target_failure = tests/test_device_registration_flow.py::test_unbind_self_prioritizes_active_serial_target
targeted_test = 1 passed
device_registration_flow = 18 passed
full_pytest = 95 passed
merge_to_master_attempted = false
git_push_attempted = false
deployment_attempted = false
```

## Diagnosis

The target failure was caused by a missing module-level dependency seam in `backend/api/device_api.py`.

The test patches:

```text
device_api.get_care_service
```

but the route previously imported `get_care_service` inside `unbind_device_self`, so the module did not expose a patchable `get_care_service` attribute. This caused:

```text
AttributeError: module 'backend.api.device_api' has no attribute 'get_care_service'
```

The actual self-unbind business logic did not require changes.

## Change Scope

Changed files:

```text
backend/api/device_api.py
```

Patch summary:

```text
Moved get_care_service into the existing module-level backend.dependencies import list.
Removed the local import inside unbind_device_self.
Did not change DeviceService.
Did not change CareService.
Did not change active serial target logic.
Did not change tests.
```

## Verification

Targeted test:

```powershell
conda run -n helth pytest tests/test_device_registration_flow.py::test_unbind_self_prioritizes_active_serial_target -q
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
18 passed
```

Full regression:

```powershell
conda run -n helth pytest
```

Result:

```text
95 passed
```

## Boundary Confirmation

```text
device_service_touched = false
care_service_touched = false
active_serial_target_logic_touched = false
test_assertion_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
merge_to_master_attempted = false
```

## Approval Request

This branch is ready for leader review. If approved, merge `lobster/device-registration-flow-fix-unbind-self-seam-001` into `master`, rerun the targeted test, rerun `tests/test_device_registration_flow.py -q`, and rerun full pytest.
