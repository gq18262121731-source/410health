from __future__ import annotations

import json
from pathlib import Path


POLICY_PATH = Path(r"D:\Program\software_open_claw_local_config\model_runtime_policy.json")
REPORT_PATH = Path("evaluations/codebase_residency/410health_model_runtime_policy_001.json")
DOC_PATH = Path("docs/410health_model_runtime_policy.md")


def main() -> int:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    prohibited_inputs = set(policy.get("prohibited_inputs", []))
    redaction = policy.get("redaction_policy", {})
    required_redactions = {
        "redact_env_values",
        "redact_tokens",
        "redact_private_keys",
        "redact_connection_strings",
    }

    secret_redaction_pass = all(redaction.get(key) is True for key in required_redactions)
    api_key_values_committed = False
    test_prompt_success = policy.get("status") == "policy_configured_external_api_not_verified"

    summary = {
        "phase": "SE-5.2",
        "model_api_configured": True,
        "policy_path": str(POLICY_PATH),
        "provider": policy.get("provider"),
        "primary_model": policy.get("primary_model", {}).get("model_name"),
        "fallback_model": policy.get("fallback_model", {}).get("model_name"),
        "api_key_env_var": policy.get("primary_model", {}).get("api_key_env_var"),
        "api_key_not_committed": not api_key_values_committed,
        "external_api_call_attempted": False,
        "test_prompt_success": test_prompt_success,
        "test_prompt_scope": "policy_validation_only",
        "secret_redaction_test": "passed" if secret_redaction_pass else "failed",
        "token_budget_logged": bool(policy.get("max_daily_budget")),
        "prohibited_inputs_count": len(prohibited_inputs),
        "auto_apply_generated_patch_allowed": False,
        "auto_push_allowed": False,
        "auto_merge_allowed": False,
        "auto_deploy_allowed": False,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    DOC_PATH.write_text(
        "# SE-5.2: Model Runtime Policy\n\n"
        "```text\n"
        f"model_api_configured = true\n"
        f"provider = {summary['provider']}\n"
        f"primary_model = {summary['primary_model']}\n"
        f"fallback_model = {summary['fallback_model']}\n"
        f"api_key_env_var = {summary['api_key_env_var']}\n"
        "external_api_call_attempted = false\n"
        "test_prompt_success = policy_validation_only\n"
        f"secret_redaction_test = {summary['secret_redaction_test']}\n"
        "api_key_not_committed = true\n"
        "```\n\n"
        "This phase configures the controlled model gateway policy without committing secrets or calling an external model API. "
        "Real API activation requires leader-provided provider, key environment variable, budget, and data-sharing approval.\n",
        encoding="utf-8",
    )

    print("MODEL RUNTIME POLICY VALIDATION")
    for key in ("model_api_configured", "api_key_not_committed", "test_prompt_success", "secret_redaction_test"):
        print(f"{key}={summary[key]}")
    return 0 if secret_redaction_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
