# 410health Sandbox Bugfix Trial 004 Report

## Phase

SE-0.6: Sandbox Bugfix Trial 004

## Result

Ready for leader review.

This trial used a dedicated Git test branch and fixed one narrow failure:

```text
branch = lobster/sandbox-bugfix-trial-004
target_failure = tests/test_omni_logic.py::test_omni_chat_aggregates_text_and_wraps_pcm_audio
failure_before = omni request used a generic system prompt instead of the elder voice safety prompt
```

## Diagnosis

The Omni text aggregation and PCM-to-WAV wrapping logic were already working. The failure was in prompt wrapping:

```text
expected = elder-specific warm and safe system prompt
actual = You are a helpful assistant.
```

`VoiceService.omni_chat` already built `system_prompt`, but the outbound message still used a hard-coded generic assistant prompt.

## Change Scope

Changed files:

```text
backend/services/voice_service.py
tests/test_omni_logic.py
```

Changes made:

```text
1. Use the constructed system_prompt as the outbound system message.
2. Align test assertions with the current Chinese elder voice prompt safety wording.
```

Device serial flow, alarm service, and LangChain RAG manifest logic were not touched.

## Verification

Targeted rerun:

```text
command = conda run -n helth pytest tests/test_omni_logic.py::test_omni_chat_aggregates_text_and_wraps_pcm_audio -q
result = passed
summary = 1 passed
```

Full pytest rerun:

```text
command = conda run -n helth pytest
result = failed
summary = 85 passed, 10 failed
```

Compared with the previous master state of `84 passed, 11 failed`, this trial removes the Omni prompt wrapping failure without touching unrelated clusters.

Remaining failure clusters:

```text
alarm service SOS dedupe
device serial target registration and switch flow
LangChain RAG manifest shape
```

These were not modified in this trial.

## Safety Boundary

```text
master_merged = false
device_serial_flow_touched = false
alarm_service_touched = false
rag_manifest_touched = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
prohibited_command_detected = false
leader_approval_required_before_merge = true
```

## Approval Request

Please review this branch before any merge:

```text
lobster/sandbox-bugfix-trial-004
```

Recommended next action after approval:

```text
merge this branch into master, then select the next small failure cluster
```
