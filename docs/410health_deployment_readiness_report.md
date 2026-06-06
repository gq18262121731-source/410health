# SE-4.8: 410health Deployment Readiness Report

## Summary

```text
phase = SE-4.8
result = readiness_created_not_deployed
actual_deployment_attempted = false
```

This report prepares deployment knowledge only. No production service was started, no server was modified, and no public port was opened.

## Backend

Recommended local/staging start command:

```powershell
conda run -n helth uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Known backend defaults from `backend/config.py`:

```text
port = 8000
data_mode = mock
serial_enabled = false
mqtt_enabled = false
mqtt_broker_host = localhost
mqtt_broker_port = 1883
ollama_base_url = http://localhost:11434
```

Health check:

```text
GET /healthz
```

## Frontend

Build command:

```powershell
npm run check --prefix frontend/vue-dashboard
```

The command runs:

```text
typecheck
lint
vite build
```

Current frontend build status:

```text
frontend_check = passed
oversized_js_chunks = 0
```

## Environment Variables

Known runtime configuration is loaded through `backend/config.py` and `.env`.

Required before real deployment:

```text
review .env values
populate .env.example with non-secret placeholders
confirm AI provider keys
confirm serial / mqtt mode
confirm CORS policy
confirm data directory / persistence policy
```

Do not print or commit real secrets.

## Rollback

Preferred rollback:

```text
git revert <deployment_commit>
restore prior deployment artifact
restart service only after leader approval
```

Backup recommendation before first deployment:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$src = "D:\Program\410health"
$backup = "D:\Program\410health_backups\410health_pre_deploy_$timestamp"
robocopy $src $backup /E /XD .git node_modules venv .venv __pycache__ dist build target
```

## Deployment Blockers

```text
production host not selected
service manager not selected
env/secrets review not completed
public exposure / CORS policy not approved
OpenClaw Gateway service config warning unresolved
rollback drill not executed
```

## Boundary

```text
actual_deployment_attempted = false
production_service_started = false
production_config_changed = false
public_port_opened = false
dependency_install_attempted = false
git_push_attempted = false
```
