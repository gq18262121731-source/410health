# 410health Device Registration Flow Active Target Fix Merge Report

## Summary

Phase SE-1.0A-C / Approved Merge for Active Serial Target Semantics Fix is complete.

```text
source_branch = lobster/device-registration-flow-fix-active-target-001
target_branch = master
merge_executed = true
merge_commit = 49e55de
active_target_tests = 6 passed
device_registration_flow = 16 passed, 2 failed
full_pytest = 93 passed, 2 failed
new_failure_detected = false
```

## Approved Change

This merge updates active serial target semantics in `DeviceService`.

The active serial target now represents the current physical serial data source, not only a serial device that is already bound to an elder account.

Merged behavior:

```text
SERIAL + not DISABLED = eligible active serial target
MOCK / BLE = rejected
DISABLED = rejected
```

Changed files merged:

```text
backend/services/device_service.py
docs/410health_device_registration_flow_active_target_fix_report.md
evaluations/codebase_residency/410health_device_registration_flow_active_target_fix_001.json
```

## Master Verification

The six active target tests passed on `master`:

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

Remaining known failures:

```text
tests/test_device_registration_flow.py::test_demo_directory_strictly_matches_setup_account_layout
tests/test_device_registration_flow.py::test_unbind_self_prioritizes_active_serial_target
```

## Boundary Confirmation

```text
demo_directory_test_touched = false
unbind_self_seam_touched = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```

## Result

The active serial target semantics fix has been merged into `master` under leader approval. Master is verified at `93 passed, 2 failed`, with no new failure detected.
