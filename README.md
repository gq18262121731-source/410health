# AIoT Health Monitoring Demo

AIoT elder-care monitoring demo built around:

- `FastAPI` backend
- `Vue 3` dashboard frontend
- `Flutter` mobile shell
- local/device health analysis and agent-assisted interpretation

## Current focus

The repo is currently in a formal business-flow integration stage. The most important active threads are:

- formal elder registration
- formal family registration
- elder-family relation binding
- device register / bind / unbind / rebind / delete
- frontend-backend contract alignment
- agent output cleanup and UI presentation hardening

## Environment rule

This project must not mix Python environments.

Mandatory rule:

- always use the conda environment `helth`
- do not run bare `python`
- do not run bare `pytest`
- do not assume the active shell is already correct
- do not assume a newly opened coding-agent shell starts inside `helth`

Use:

```powershell
conda run -n helth python ...
conda run -n helth pytest ...
```

The expected interpreter is:

```text
C:\Users\13010\anaconda3\envs\helth\python.exe
```

If a command runs under any other interpreter, treat that as an execution mistake and rerun it in `helth`.

Important note about the current machine:

- bare `python` may resolve to `F:\Python3.13\python.exe`
- bare `pytest` may resolve to `C:\Users\13010\anaconda3\Scripts\pytest.exe`
- newly spawned coding agents may inherit this ambient shell state instead of `helth`

Therefore:

- every Python command must be run as `conda run -n helth python ...`
- every pytest command must be run as `conda run -n helth pytest ...`
- if a command was run without that prefix, treat the result as untrusted and rerun it correctly

## Quick start

## Fixed command set

Use these commands as the project-standard commands. All of them are pinned to `helth`.

### Backend start

```powershell
conda run -n helth powershell -ExecutionPolicy Bypass -File .\scripts\start_server.ps1
```

### Frontend start

```powershell
conda run -n helth powershell -ExecutionPolicy Bypass -File .\scripts\start_frontend.ps1
```

### Pytest

```powershell
conda run -n helth pytest
```

### Smoke test

```powershell
conda run -n helth powershell -ExecutionPolicy Bypass -File .\scripts\run_smoke_tests.ps1 -BuildFrontend
```

### Backend HTTP smoke check

```powershell
conda run -n helth powershell -ExecutionPolicy Bypass -File .\scripts\smoke_backend_http.ps1
```

### Backend

```powershell
conda run -n helth powershell -ExecutionPolicy Bypass -File .\scripts\start_server.ps1
```

### Frontend

```powershell
conda run -n helth powershell -ExecutionPolicy Bypass -File .\scripts\start_frontend.ps1
```

### Smoke checks

```powershell
conda run -n helth powershell -ExecutionPolicy Bypass -File .\scripts\run_smoke_tests.ps1 -BuildFrontend
```

## Repo layout

- `backend/`: FastAPI routes, models, services
- `agent/`: agent orchestration, prompting, analysis assembly
- `ai/`: anomaly detection, scoring, synthetic data generation
- `frontend/vue-dashboard/`: Vue dashboard
- `mobile/flutter_app/`: Flutter client shell
- `iot/`: parser and device-side integration adapters
- `tests/`: API and behavior regression coverage
- `docs/`: architecture, contracts, handoff, and working notes

## Key docs

### Handoff and collaboration

- [Next Agent Handoff](docs/next-agent-handoff.md)
- [Frontend Backend Agent Collaboration Contract](docs/agent-collaboration-contract.md)
- [Collaboration Gap Task Board](docs/collaboration-gap-task-board.md)

### Architecture and setup

- [Architecture](docs/architecture.md)
- [Environment Setup](docs/env-setup.md)
- [Current Logic Analysis](docs/current-logic-analysis.md)

## Working rules

- Treat `docs/agent-collaboration-contract.md` as the source of truth for frontend-backend-agent coordination.
- If behavior changes in registration, relation, device ownership, or agent output shape, update:
  1. code
  2. regression tests
  3. the contract doc
- Use `docs/collaboration-gap-task-board.md` as the live unresolved-gap board.
- Use `docs/next-agent-handoff.md` for a fast situational handoff to the next coding agent.

## Tests

Run all tests:

```powershell
conda run -n helth pytest
```

Recommended high-signal files:

- `tests/test_registration_flow_api.py`
- `tests/test_care_auth_api.py`
- `tests/test_chat_api.py`
- `tests/test_agent_analysis.py`
