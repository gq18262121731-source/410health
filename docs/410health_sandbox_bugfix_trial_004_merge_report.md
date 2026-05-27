# 410health Sandbox Bugfix Trial 004 Merge Report

## Phase

SE-0.6C: Approved Merge for Sandbox Bugfix Trial 004

## Result

Passed.

Leader approved the controlled merge of:

```text
source_branch = lobster/sandbox-bugfix-trial-004
target_branch = master
merge_strategy = --no-ff
merge_commit = 8056829a8c757d0b060af8e6fc4c61cf8cbcb055
merge_message = fix: use elder safety system prompt in omni chat
```

## Merged Scope

The merge brought in one small Omni prompt wrapping fix plus its test and audit records:

```text
backend/services/voice_service.py
tests/test_omni_logic.py
docs/410health_sandbox_bugfix_trial_004_report.md
evaluations/codebase_residency/410health_sandbox_bugfix_trial_004.json
```

The change makes `VoiceService.omni_chat` send the constructed elder safety `system_prompt` as the outbound system message. It does not change text aggregation or PCM-to-WAV wrapping.

Device serial flow, alarm service, and LangChain RAG manifest logic were not touched.

## Verification on master

Targeted test:

```text
command = conda run -n helth pytest tests/test_omni_logic.py::test_omni_chat_aggregates_text_and_wraps_pcm_audio -q
result = passed
summary = 1 passed
```

Full pytest:

```text
command = conda run -n helth pytest
result = failed
summary = 85 passed, 10 failed
```

This is the expected post-merge state. The Omni prompt wrapping test remains green on master, and the remaining 10 failures are pre-existing failure clusters intentionally left untouched in this merge.

Remaining failure clusters:

```text
alarm service SOS dedupe
device serial target registration and switch flow
LangChain RAG manifest shape
```

## Safety Boundary

```text
new_failure_detected = false
device_serial_flow_touched = false
alarm_service_touched = false
rag_manifest_touched = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
remote_connected = false
```

## Next Step

Start a new sandbox branch for the next small failure cluster. Recommended next target:

```text
tests/test_langchain_rag_service.py::test_rag_service_writes_manifest_when_vector_store_is_ready
```

Continue to defer the device serial flow cluster until the isolated failures are cleared.
