# 410health Device Registration Flow Active Target Fix Report

## Summary

Phase SE-1.0A / Active Serial Target Semantics Fix is complete and waiting for leader review.

```text
branch = lobster/device-registration-flow-fix-active-target-001
target_cluster = active serial target semantics
targeted_active_target_tests = 6 passed
device_registration_flow = 16 passed, 2 failed
full_pytest = 93 passed, 2 failed
merge_to_master_attempted = false
git_push_attempted = false
deployment_attempted = false
```

## Diagnosis

SE-0.9 mapped six failures to a shared active serial target semantics mismatch.

The old service behavior treated active serial target as:

```text
SERIAL + BOUND + user_id present + not DISABLED
```

The tests and surrounding serial flow expect active serial target to mean:

```text
current physical SERIAL data source + not DISABLED
```

That distinction matters because a real serial device can be the active ingest source before it is bound to an elder account.

## Change Scope

Changed files:

```text
backend/services/device_service.py
```

Patch summary:

```text
_set_active_serial_target_locked now accepts unbound SERIAL devices.
_refresh_active_serial_target_locked now considers unbound SERIAL devices.
DISABLED devices are still rejected.
MOCK / BLE devices are still rejected.
No tests were changed.
```

## Targeted Verification

All six active target tests passed:

```text
test_latest_serial_registration_becomes_active_target_and_falls_back_on_delete = passed
test_register_serial_device_without_binding_is_allowed_even_when_elder_has_same_model = passed
test_can_switch_active_serial_target_explicitly = passed
test_serial_target_switch_api_returns_new_target = passed
test_binding_existing_serial_device_makes_it_active_target_even_if_newer_target_exists = passed
test_rebinding_existing_serial_device_makes_it_active_target_even_if_newer_target_exists = passed
```

Device registration flow regression:

```powershell
conda run -n helth pytest tests/test_device_registration_flow.py -q
```

Result:

```text
16 passed, 2 failed
```

Full regression:

```powershell
conda run -n helth pytest
```

Result:

```text
93 passed, 2 failed
```

## Remaining Known Failures

The remaining two failures are the independent SE-1.0B / SE-1.0C items identified in SE-0.9:

```text
test_demo_directory_strictly_matches_setup_account_layout
  reason = demo directory test variable name mismatch

test_unbind_self_prioritizes_active_serial_target
  reason = device_api.get_care_service dependency seam is not module-level monkeypatchable
```

## Boundary Confirmation

```text
demo_directory_test_touched = false
unbind_self_seam_touched = false
alarm_service_touched = false
rag_manifest_service_touched = false
omni_logic_touched = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
merge_to_master_attempted = false
```

## Approval Request

This branch is ready for leader review. If approved, merge `lobster/device-registration-flow-fix-active-target-001` into `master`, rerun the six active target tests, rerun `tests/test_device_registration_flow.py -q`, and rerun full pytest.
