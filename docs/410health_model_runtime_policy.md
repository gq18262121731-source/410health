# SE-5.2: Model Runtime Policy

```text
model_api_configured = true
provider = openclaw_default_runtime
primary_model = deepseek-ai/DeepSeek-V3.2
fallback_model = summary_triage_model
api_key_env_var = OPENCLAW_MODEL_API_KEY
external_api_call_attempted = false
test_prompt_success = policy_validation_only
secret_redaction_test = passed
api_key_not_committed = true
```

This phase configures the controlled model gateway policy without committing secrets or calling an external model API. Real API activation requires leader-provided provider, key environment variable, budget, and data-sharing approval.
