# 410health Sandbox Bugfix Trial 006 Merge Report

## Summary

Phase SE-0.8C / Approved Merge for Sandbox Bugfix Trial 006 is complete.

```text
source_branch = lobster/sandbox-bugfix-trial-006
target_branch = master
merge_executed = true
merge_commit = bc7a1ad
targeted_test = 1 passed
alarm_service_tests = 8 passed
full_pytest = 87 passed, 8 failed
new_failure_detected = false
```

## Approved Change

Trial 006 fixed the active SOS dedupe calculation in `AlarmService`.

The old logic compared the active SOS alarm timestamp with wall-clock `now`, which caused fixed historical test events to look stale. The merged change compares the incoming SOS event timestamp with the existing active SOS timestamp instead:

```text
age = max(timedelta(0), alarm.created_at - existing.created_at)
```

Changed files merged:

```text
backend/services/alarm_service.py
docs/410health_sandbox_bugfix_trial_006_report.md
evaluations/codebase_residency/410health_sandbox_bugfix_trial_006.json
```

## Master Verification

Targeted verification on `master`:

```powershell
conda run -n helth pytest tests/test_alarm_service.py::test_alarm_service_dedupes_active_sos_alarm -q
```

Result:

```text
1 passed
```

Alarm service regression on `master`:

```powershell
conda run -n helth pytest tests/test_alarm_service.py -q
```

Result:

```text
8 passed
```

Full regression on `master`:

```powershell
conda run -n helth pytest
```

Result:

```text
87 passed, 8 failed
```

Remaining known failures are concentrated in:

```text
tests/test_device_registration_flow.py serial target registration and switch flow
```

## Boundary Confirmation

```text
device_serial_flow_touched = false
rag_manifest_service_touched = false
omni_logic_touched = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```

## Result

Trial 006 has been merged into `master` under leader approval. Master is verified at `87 passed, 8 failed`, with no new failure detected.
