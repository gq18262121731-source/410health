# 410health Sandbox Bugfix Trial 006 Report

## Summary

Phase SE-0.8 / Sandbox Bugfix Trial 006 is complete and waiting for leader review.

```text
branch = lobster/sandbox-bugfix-trial-006
target_failure = tests/test_alarm_service.py::test_alarm_service_dedupes_active_sos_alarm
targeted_test = 1 passed
alarm_service_tests = 8 passed
full_pytest = 87 passed, 8 failed
merge_to_master_attempted = false
git_push_attempted = false
deployment_attempted = false
```

## Diagnosis

The target failure was caused by an SOS dedupe logic defect, not a stale test fixture.

The service used the current wall-clock time to decide whether an existing active SOS alarm was older than the dedupe window. The target test builds fixed timestamps:

```text
first.created_at = 2026-03-25T01:00:00Z
second.created_at = first.created_at + 8 seconds
dedupe_window = 15 seconds
```

Because the old logic compared `datetime.now(timezone.utc)` with `existing.created_at`, the existing alarm looked stale even though the incoming SOS event was only 8 seconds later. That allowed a duplicate SOS to be emitted and pushed.

The correct comparison for repeated packet dedupe is the incoming alarm time against the existing alarm time.

## Change Scope

Changed files:

```text
backend/services/alarm_service.py
```

Patch summary:

```text
Changed active SOS dedupe age calculation from wall-clock time to incoming event time.
Removed the now variable that became unused.
Did not change queue behavior, notification dispatch, acknowledgment, or cooldown APIs.
Did not touch device serial flow.
```

## Verification

Targeted test:

```powershell
conda run -n helth pytest tests/test_alarm_service.py::test_alarm_service_dedupes_active_sos_alarm -q
```

Result:

```text
1 passed
```

Alarm service regression:

```powershell
conda run -n helth pytest tests/test_alarm_service.py -q
```

Result:

```text
8 passed
```

Full regression:

```powershell
conda run -n helth pytest
```

Result:

```text
87 passed, 8 failed
```

Remaining known failures are now concentrated in:

```text
tests/test_device_registration_flow.py serial target registration and switch flow
```

## Boundaries

```text
device_serial_flow_touched = false
rag_manifest_service_touched = false
omni_logic_touched = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
merge_to_master_attempted = false
```

## Approval Request

This branch is ready for leader review. If approved, merge `lobster/sandbox-bugfix-trial-006` into `master` with a controlled no-fast-forward merge, then rerun the targeted alarm service test and full pytest on `master`.
