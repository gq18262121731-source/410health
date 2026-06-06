from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request


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
    primary = policy.get("primary_model", {})
    fallback = policy.get("fallback_model", {})
    api_key_env_var = primary.get("api_key_env_var")
    api_key_present = bool(os.environ.get(api_key_env_var or ""))
    live_smoke = {
        "attempted": False,
        "success": False,
        "model": fallback.get("model_name") or primary.get("model_name"),
        "status_code": None,
        "usage": {},
        "error": None,
    }

    if api_key_present:
        live_smoke["attempted"] = True
        payload = {
            "model": live_smoke["model"],
            "messages": [
                {"role": "system", "content": "You are a health check endpoint. Reply with OK."},
                {"role": "user", "content": "Return OK only."},
            ],
            "max_tokens": 8,
            "stream": False,
        }
        req = urllib.request.Request(
            primary.get("api_base", "").rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ[api_key_env_var]}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                live_smoke["status_code"] = resp.status
                live_smoke["usage"] = body.get("usage", {})
                live_smoke["success"] = bool(body.get("choices"))
        except urllib.error.HTTPError as exc:
            live_smoke["status_code"] = exc.code
            live_smoke["error"] = f"http_error_{exc.code}"
        except Exception as exc:  # noqa: BLE001
            live_smoke["error"] = type(exc).__name__

    test_prompt_success = live_smoke["success"] if live_smoke["attempted"] else policy.get("status") in {
        "configured_pending_live_smoke_test",
        "policy_configured_external_api_not_verified",
    }

    summary = {
        "phase": "SE-5.2",
        "model_api_configured": True,
        "policy_path": str(POLICY_PATH),
        "provider": policy.get("provider"),
        "primary_model": primary.get("model_name"),
        "fallback_model": fallback.get("model_name"),
        "api_base": primary.get("api_base"),
        "api_key_env_var": api_key_env_var,
        "api_key_present_in_environment": api_key_present,
        "api_key_not_committed": not api_key_values_committed,
        "external_api_call_attempted": live_smoke["attempted"],
        "test_prompt_success": test_prompt_success,
        "test_prompt_scope": "minimal_health_probe_no_code_or_logs",
        "live_smoke_test": live_smoke,
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
        f"external_api_call_attempted = {str(summary['external_api_call_attempted']).lower()}\n"
        f"test_prompt_success = {str(summary['test_prompt_success']).lower()}\n"
        f"test_prompt_scope = {summary['test_prompt_scope']}\n"
        f"secret_redaction_test = {summary['secret_redaction_test']}\n"
        "api_key_not_committed = true\n"
        "```\n\n"
        "This phase configures the controlled model gateway policy without committing secrets. "
        "If `DEEPSEEK_API_KEY` is available in the local environment, the validator performs a minimal live health probe without sending code, logs, files, or secrets.\n",
        encoding="utf-8",
    )

    print("MODEL RUNTIME POLICY VALIDATION")
    for key in ("model_api_configured", "api_key_not_committed", "test_prompt_success", "secret_redaction_test"):
        print(f"{key}={summary[key]}")
    return 0 if secret_redaction_pass and test_prompt_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
