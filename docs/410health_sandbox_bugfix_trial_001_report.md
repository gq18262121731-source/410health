# 410health Sandbox Bugfix Trial 001 Report

## Phase

SE-0.3B: Sandbox Bugfix Trial

## Result

Ready for leader review.

This trial used a dedicated Git test branch and fixed one narrow test failure:

```text
branch = lobster/sandbox-bugfix-trial-001
target_failure = tests/test_rag_incremental.py::test_incremental_rag
failure_before = NameError: MagicMock is not defined
```

## Change Scope

Only one test file was changed:

```text
tests/test_rag_incremental.py
```

Changes made:

```text
1. Import MagicMock at module scope so pytest execution can access it.
2. Use pytest tmp_path for temporary knowledge and Chroma directories.
3. Remove project-root temp directory deletion from the test.
```

No production service code was changed.

## Verification

Targeted rerun:

```text
command = conda run -n helth pytest tests/test_rag_incremental.py -q
result = passed
summary = 1 passed
```

Full pytest rerun:

```text
command = conda run -n helth pytest
result = failed
summary = 82 passed, 13 failed
```

Compared with the SE-0.2 baseline of `81 passed, 14 failed`, this trial removes the `test_rag_incremental.py` failure without expanding the change scope.

Remaining failure clusters:

```text
alarm service SOS dedupe
demo persona names
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
prohibited_command_detected = false
leader_approval_required_before_merge = true
```

## Approval Request

Please review this branch before any merge:

```text
lobster/sandbox-bugfix-trial-001
```

Recommended next action after approval:

```text
merge this branch into master, then select the next small failure cluster
```
