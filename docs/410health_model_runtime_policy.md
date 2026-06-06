# SE-5.2: Model Runtime Policy

```text
model_api_configured = true
provider = deepseek
primary_model = deepseek-v4-pro
fallback_model = deepseek-v4-flash
api_key_env_var = DEEPSEEK_API_KEY
external_api_call_attempted = true
test_prompt_success = true
test_prompt_scope = minimal_health_probe_no_code_or_logs
secret_redaction_test = passed
api_key_not_committed = true
```

This phase configures the controlled model gateway policy without committing secrets. If `DEEPSEEK_API_KEY` is available in the local environment, the validator performs a minimal live health probe without sending code, logs, files, or secrets.
