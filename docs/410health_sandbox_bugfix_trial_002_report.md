# 410health Sandbox Bugfix Trial 002 Report

## Phase

SE-0.4: Sandbox Bugfix Trial 002

## Result

Ready for leader review.

This trial used a dedicated Git test branch and fixed one narrow test failure:

```text
branch = lobster/sandbox-bugfix-trial-002
target_failure = tests/test_demo_overlay.py::test_mock_generator_personas_follow_setup_subject_names
failure_before = expected legacy names, but generator follows setup names
```

## Change Scope

Only one test file was changed:

```text
tests/test_demo_overlay.py
```

Change made:

```text
Updated the expected first three mock persona names to match setup.md and backend/services/care_service.py:
李四 / 王五 / 赵六
```

No production service code was changed.

## Verification

Targeted rerun:

```text
command = conda run -n helth pytest tests/test_demo_overlay.py::test_mock_generator_personas_follow_setup_subject_names -q
result = passed
summary = 1 passed
```

Full pytest rerun:

```text
command = conda run -n helth pytest
result = failed
summary = 83 passed, 12 failed
```

Compared with the previous master state of `82 passed, 13 failed`, this trial removes the demo overlay persona mismatch without touching device serial flow or unrelated clusters.

Remaining failure clusters:

```text
alarm service SOS dedupe
device serial target registration and switch flow
LangChain RAG manifest shape
Omni warm prompt expectation
RAG trigger heuristic
```

These were not modified in this trial.

## Safety Boundary

```text
master_merged = false
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
device_serial_flow_touched = false
prohibited_command_detected = false
leader_approval_required_before_merge = true
```

## Approval Request

Please review this branch before any merge:

```text
lobster/sandbox-bugfix-trial-002
```

Recommended next action after approval:

```text
merge this branch into master, then select the next small failure cluster
```
