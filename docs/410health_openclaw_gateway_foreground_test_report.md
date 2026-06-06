# SE-4.3: Controlled OpenClaw Gateway Start Report

## Summary

```text
phase = SE-4.3
result = passed_with_service_config_warning
gateway_listening = true
gateway_health = OK
gateway_bind = 127.0.0.1
gateway_port = 18789
remote_exposure = false
```

## Verification

```text
openclaw --version = OpenClaw 2026.6.1 (2e08f0f)
openclaw config validate = passed
openclaw gateway health = OK
openclaw gateway status = connectivity probe ok
dashboard = http://127.0.0.1:18789/
```

The gateway is reachable through local loopback only:

```text
probe_target = ws://127.0.0.1:18789
listening = 127.0.0.1:18789
tailscale_exposure = off
```

## Service Observation

OpenClaw reports an existing Scheduled Task Gateway service:

```text
service_registered = true
runtime = running
gateway_version = 2026.6.1
service_installed_by_this_phase = false
daemon_install_attempted = false
```

This phase did not install a daemon. The existing service was already present and is now running. OpenClaw also reports service config warnings:

```text
service_config_out_of_date = true
service_installed_by_older_openclaw = 2026.4.19-beta.2
service_config_contains_managed_env_values = true
doctor_repair_attempted = false
```

No key or secret value was printed or copied into this report.

## Boundary

```text
remote_exposure_enabled = false
daemon_install_attempted = false
doctor_repair_attempted = false
channel_registration_attempted = false
business_code_changed = false
dependency_install_attempted = false
deployment_attempted = false
git_push_attempted = false
```

## Next Step

Before treating the Gateway service as production-ready, request approval for one of:

```text
keep_current_service_as_local_only
run openclaw doctor in inspect-only mode
repair/reinstall gateway service
stop gateway after test
```

Do not expose the Gateway beyond loopback without explicit approval.
