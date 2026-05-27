# 410health Sandbox Bugfix Trial 005 Report

## Summary

Phase SE-0.7 / Sandbox Bugfix Trial 005 is complete and waiting for leader review.

```text
branch = lobster/sandbox-bugfix-trial-005
target_failure = tests/test_langchain_rag_service.py::test_rag_service_writes_manifest_when_vector_store_is_ready
targeted_test = 1 passed
full_pytest = 86 passed, 9 failed
merge_to_master_attempted = false
git_push_attempted = false
deployment_attempted = false
```

## Diagnosis

The target failure was caused by a stale test expectation for the persisted LangChain RAG manifest shape.

Current service behavior writes `payload["files"]` as a source-keyed object:

```text
files = {
  "faq.md": {
    "source": "faq.md",
    ...
  }
}
```

The failing test still expected a legacy list shape:

```text
payload["files"][0]["source"]
```

`LangChainRAGService` already contains backward-compatible loading for older list manifests, while the current writer stores a keyed object for incremental lookup. Therefore this trial aligned the test assertion with the current persisted manifest contract instead of changing service logic.

## Change Scope

Changed files:

```text
tests/test_langchain_rag_service.py
```

Patch summary:

```text
Updated the manifest assertion to read payload["files"]["faq.md"]["source"].
No production service code changed.
No device serial flow touched.
No alarm service touched.
No omni logic touched.
```

## Verification

Targeted test:

```powershell
conda run -n helth pytest tests/test_langchain_rag_service.py::test_rag_service_writes_manifest_when_vector_store_is_ready -q
```

Result:

```text
1 passed
```

Full regression:

```powershell
conda run -n helth pytest
```

Result:

```text
86 passed, 9 failed
```

Remaining failure clusters are recorded as known follow-up work:

```text
tests/test_alarm_service.py::test_alarm_service_dedupes_active_sos_alarm
tests/test_device_registration_flow.py::* serial target registration and switch flow
```

## Boundaries

```text
business_code_changed = false
device_serial_flow_touched = false
alarm_service_touched = false
omni_logic_touched = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
merge_to_master_attempted = false
```

## Approval Request

This branch is ready for leader review. If approved, merge `lobster/sandbox-bugfix-trial-005` into `master` with a controlled no-fast-forward merge, then rerun the targeted test and full pytest on `master`.
