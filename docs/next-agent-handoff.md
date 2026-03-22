# Next Agent Handoff

Last updated: 2026-03-21

## What this repo is doing now

This project is an AIoT elder-care monitoring demo with a FastAPI backend and a Vue dashboard frontend.

The active integration areas are:

- formal user registration
- elder-family relation binding
- device ownership lifecycle
- frontend/backend contract enforcement
- agent output cleanup and operator-facing presentation
- offline local model runtime for LAN deployment
- stable time-range device health report generation

## Read these first

Read in this order:

1. `docs/next-agent-handoff.md`
2. `docs/collaboration-gap-task-board.md`
3. `docs/agent-collaboration-contract.md`
4. `docs/fixed-commands.md` before running commands
5. then only the code and tests directly related to the task you pick up

## Hard environment rule

Do not mix environments in this repo.

Mandatory execution rule:

- always run Python and pytest commands in conda env `helth`
- do not use bare `python`
- do not use bare `pytest`
- if you are unsure which interpreter is active, use `conda run -n helth ...` explicitly
- do not assume a newly spawned coding agent starts inside `helth`

Use:

```powershell
conda run -n helth python ...
conda run -n helth pytest ...
```

Expected interpreter:

```text
C:\Users\13010\anaconda3\envs\helth\python.exe
```

If any command runs under another interpreter, stop and rerun it correctly.

Current machine caveat:

- bare `python` may resolve to `F:\Python3.13\python.exe`
- bare `pytest` may resolve to `C:\Users\13010\anaconda3\Scripts\pytest.exe`
- new coding agents can inherit this ambient shell state

So:

- never trust the default shell interpreter
- always use `conda run -n helth ...` for Python and pytest
- if a result came from a bare command, rerun it before using it

## Current source-of-truth docs

### Contract

- `docs/agent-collaboration-contract.md`

Use this for:

- business rules
- permission rules
- API expectations
- agent response expectations
- change protocol

### Open gap board

- `docs/collaboration-gap-task-board.md`

Use this for:

- unresolved frontend gaps
- unresolved test gaps
- unresolved health-model gaps
- anything that still does not match the contract

Completed items should be removed from that file.

### Offline model runtime

- `docs/local-model-runtime.md`

Use this for:

- approved local models
- local routing behavior
- supported offline retrieval behavior
- OM-line verification targets

### Coordination docs

- `docs/dispatcher-self-workflow-zh.md`
- `docs/coordination-master-plan-zh.md`
- `docs/business-and-dispatch-overview-zh.md`
- `docs/coordination-fe-frontend-zh.md`
- `docs/coordination-ui-designer-zh.md`
- `docs/coordination-be-backend-zh.md`
- `docs/coordination-te-test-zh.md`
- `docs/coordination-dr-device-zh.md`
- `docs/coordination-ag-agent-zh.md`
- `docs/coordination-om-offline-model-zh.md`
- `docs/coordination-hm-health-model-zh.md`

Use these for:

- self dispatch and review workflow
- overall dispatch
- per-role responsibilities
- report-gate workflow
- current per-role status

## Reading order summary

Every engineer or coding agent should read documents in this order:

1. `docs/next-agent-handoff.md`
2. `docs/collaboration-gap-task-board.md`
3. `docs/agent-collaboration-contract.md`
4. `docs/fixed-commands.md` before running commands
5. then only the code files directly related to the task they pick up

Task pickup rule:

- Frontend Engineer: pick `FE-*`
- Backend Engineer: pick `BE-*`
- Test Engineer: pick `TE-*`
- Device Registration Engineer: pick `DR-*`
- UI Designer: pick `UI-*`
- Agent Engineer: pick `AG-*`
- Offline Model Engineer: pick `OM-*`
- Health Model Engineer: pick `HM-*`

Do not start from the contract doc alone.
Use the task board to decide what to do, and the contract doc to decide what correct means.

## Canonical Role Reference

Use this section as the clean role reference when terminal output renders older text incorrectly.

### Agent Engineer

- Task prefix: `AG-`
- Responsibility:
  - agent interface protocol
  - frontend/backend response-shape alignment
  - output sanitization
  - agent tool orchestration
  - agent-related test alignment

### Offline Model Engineer

- Task prefix: `OM-`
- Responsibility:
  - local model policy
  - `Qwen3:1.7B` / `Deepseek-r1:1.5B` routing
  - offline LAN runtime
  - prompt package
  - local RAG
  - knowledge-base construction

### Health Model Engineer

- Task prefix: `HM-`
- Responsibility:
  - health-score model
  - anomaly detection
  - community risk ordering
  - health-report basis
  - threshold calibration
  - health-model regression coverage

### UI Designer

- Task prefix: `UI-`
- Responsibility:
  - demo visual direction
  - typography, color, spacing, and token coherence
  - login/registration visual redesign
  - report/alarm presentation redesign
  - component and page-level polish guidance for frontend implementation

## Current code reality

### Backend

- management write APIs for user, relation, and device ownership are implemented
- public self-service registration endpoints exist for `elder`, `family`, and `community` roles
- formal login exists at `POST /api/v1/auth/login`
- bearer-auth enforcement exists for management write APIs
- management write APIs are currently available to `family`, `community`, and `admin`
- there is no standalone backend `complete profile` endpoint in the current registration chain
- current supported `资料完善` behavior is frontend-side step collection followed by one final `/auth/register/*` submission
- `GET /api/v1/care/access-profile/me` is the current backend source of truth for bound vs unbound capability gating
- device registry and bind history persist through the SQLite app database used by the backend runtime
- newly registered devices start `offline` until real ingest marks them online
- MAC validation applies consistently across register, bind, unbind, and rebind request models
- register-with-bind preserves operator audit context in bind history
- elder-device cardinality is now enforced as:
  - one elder may have multiple bound devices
  - but only one bound device per device model / `device_name`
- care-directory elder records expose both:
  - `device_mac` as the primary backward-compatible field
  - `device_macs` as the authoritative complete list
- public self-service registration does not include self-service device binding; device binding remains a logged-in management write action
- current frontend UI exposure can still be narrower than backend/API capability; do not infer backend permission rules from which page is currently mounted in the dashboard
- device list, detail, and bind-history reads remain public in the current contract and runtime
- BLE gateway HTTP contract is now defined in `docs/ble-gateway-http-contract.md`
- BLE gateway HTTP uploads are defined as MessagePack, not JSON
- `devices[]` raw frame semantics are defined as:
  - `data_type(1 byte) + ble_mac(6 bytes) + rssi(1 byte) + ble_payload(n bytes)`
- frontend report generation should use the dedicated endpoint `POST /api/v1/chat/report/device`
- frontend should not overload analyze endpoints to simulate time-range reports
- agent analysis APIs are advisory and currently unauthenticated
- delete-device API exists
- MQTT runtime mode exists for the Radioland gateway path
- BLE gateway HTTP ingest is not implemented yet, but device-registration-side prep is now documented in:
  - `docs/ble-gateway-http-prep.md`
- chosen pre-implementation policy for HTTP gateway reports in formal mode:
  - registered devices may proceed through parser -> `ingest_sample(...)`
  - unregistered devices must be quarantined, not auto-registered
- backend demo-runtime smoke was completed successfully on local `127.0.0.1:8000`
- smoke-confirmed routes include:
  - `GET /healthz`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/care/access-profile/me`
  - `POST /api/v1/chat/report/device`
- demo note:
  - `community_admin / 123456` can log in through the formal login API
  - `community` access-profile returning `binding_state = not_applicable` is expected
  - report generation is stable when the device has at least one recent sample in the requested time window

### Offline model runtime

- supported agent runtime is now local-only for the OM line
- approved local models are:
  - `qwen3:1.7b`
  - `deepseek-r1:1.5b`
- default device/family routing uses `qwen3:1.7b`
- community summary / prioritization routing uses `deepseek-r1:1.5b`
- prompt package files are now readable and role-scoped:
  - `agent/prompting.py`
  - `agent/prompt_templates.py`
- supported retrieval path is deterministic local keyword search over `docs/knowledge-base/`
- offline runtime verification now exists in:
  - `tests/test_offline_model_runtime.py`
  - `tests/test_prompt_kb_integrity.py`
- newly confirmed reality:
  - ordinary dialogue and formal health reports are still not fully split into two independent model configurations
  - they currently still share the same local model selection route, with different prompts / RAG context
  - this is now an active follow-up requirement, not just a background caveat

### Health model runtime

- intelligent anomaly scoring now uses a deterministic Transformer-style temporal attention scorer
- current intelligent-model input window is `6` samples
- current intelligent-model features are:
  - `heart_rate`
  - `temperature`
  - `blood_oxygen`
  - `systolic`
- public output fields for intelligent analysis remain unchanged for compatibility
- sustained intelligent alarms now require `鎸佺画鏃堕棿 + 寮傚父绋嬪害` rather than a single outlier point
- reproducible HM demo scenario is documented in `docs/health-model-demo-scenarios.md`
- Transformer-derived anomaly signals are now fed into report retrieval, prompt context, fallback summary, and the existing report `key_findings` / `recommendations` fields without changing the public report schema
- `HM-005` has been completed:
  - Transformer time-series signals now enter report retrieval, report prompt context, fallback summary, and the existing `summary` / `key_findings` / `recommendations` content path
  - no new public frontend-facing fields were added
  - public report schema remains unchanged

### Frontend

- login flow exists
- relation ledger exists
- register / bind / rebind / unbind are wired
- agent panels exist for family and community
- registration shell has already been split into dedicated frontend components
- public registration panel is now wired to the real public registration APIs:
  - `api.publicRegisterElder`
  - `api.publicRegisterFamily`
  - `api.publicRegisterCommunityStaff`
- successful public registration now prefills the login form for the next step
- frontend login now prefers formal login and only falls back to mock-login on a `404`
- frontend access-profile read path is already wired and degrades safely if the backend read fails
- relation-ledger delete/history areas already have stronger loading, empty, and post-action UI states
- health evaluation panel and alarm-escalation panel skeletons already exist on structured data inputs
- frontend report rendering skeleton is prepared around the structured report contract
- UI baseline and demo-facing redesign work are now completed for the first pass:
  - `frontend/vue-dashboard/src/demo-theme.css`
  - `frontend/vue-dashboard/src/components/PublicRegistrationPanel.vue`
  - `frontend/vue-dashboard/src/components/HealthEvaluationPanel.vue`
  - `frontend/vue-dashboard/src/components/AlarmEscalationPanel.vue`
  - `docs/demo-ui-polish-spec.md`
- login-entry redesign and animated-background delivery are now also present:
  - `docs/login-animated-background-spec.md`
  - `docs/login-animated-background-delivery.md`
  - `frontend/vue-dashboard/src/assets/login-medical-backdrop.svg`
- the login page now has:
  - a centered light glassmorphism card
  - a rebuilt login/register structure
  - a background system with base image + SVG ECG line + gradient sweep
  - lighter mobile downgrade behavior
- main remaining frontend problems are:
  - final report-page rendering and protocol consumption cleanup
  - operator-facing cleanup and polish
  - final browser-side verification of Chinese text quality in the report page
  - determining whether any remaining report-text Chinese issues come from backend payload text or terminal decoding
- current conclusion from the UI line:
  - first-pass demo visual baseline is already in place
  - terminal Chinese garbling observed during review was a PowerShell display issue, not confirmed UTF-8 source corruption
  - `UI-008` and `UI-009` have been completed and should not remain on the open gap board
- a dedicated `UI-*` role now exists because visual quality has become a demo risk by itself, not just a frontend implementation detail
- runtime availability on local `:8000` can drift during collaboration; verify before concluding a frontend task is blocked by backend downtime
- latest local runtime spot-check after the frontend report showed:
  - `GET /healthz` -> `200`
  - `POST /api/v1/auth/login` with empty payload -> `422` (route exists)
  - `POST /api/v1/auth/register/family` with empty payload -> `422` (route exists)
  - `GET /api/v1/care/access-profile/me` without auth -> `401` (route exists)
- latest frontend live verification confirmed:
  - `POST /api/v1/auth/login` works
  - `POST /api/v1/auth/register/elder` works
  - `POST /api/v1/auth/register/family` works
  - `POST /api/v1/auth/register/community-staff` works
  - `GET /api/v1/care/access-profile/me` works
  - `POST /api/v1/chat/report/device` works
  - `unbound` family capability gating behaves as expected
  - `bound` family capability gating behaves as expected
  - `community` access-profile returning `not_applicable` is accepted by current frontend logic

### Tests

- registration/device lifecycle coverage is mostly present
- auth and access-profile coverage includes formal registration, formal login, and bound-vs-unbound capability checks
- bind/read policy coverage now also asserts:
  - device reads remain public
  - `family` sessions can use current management-write device APIs
  - `elder` sessions remain forbidden from management-write device APIs
- demo API-flow coverage now exists in:
  - `tests/test_demo_e2e_flow.py`
  - it covers:
    - public registration and formal login
    - family relation bind and device register/bind path
    - realtime sample visibility
    - bound access-profile health evaluation/report visibility
    - intelligent health evaluation
    - device report generation
    - sustained abnormality to active alarm and mobile push
- frontend registration-flow coverage now also exists in:
  - `tests/test_frontend_registration_flow_contract.py`
  - `docs/registration-ux-lightweight-repro.md`
  - `frontend/vue-dashboard/scripts/te006_browser_verify.mjs`
  - it covers:
    - login-page registration entry
    - panel mounting and login prefill wiring
    - elder / family / community-staff public registration branches
    - bind-now / bind-later affordance wording
- browser-level runtime artifacts for `TE-006` now exist in:
  - `tests/artifacts/te006-browser/`
  - the Playwright script uses the installed browser binary directly, so it does not depend on the outdated system drivers
- latest browser verification for `TE-006` confirmed:
  - login page visibly exposes registration entry
  - elder / family / community-staff public registration flows complete and return to login with prefills
  - browser-visible Chinese copy in this chain is readable
- latest browser verification also surfaced a frontend runtime warning cluster:
  - unresolved components reported in console:
    - `TrendChart`
    - `CommunityAssistantPanel`
    - `HealthEvaluationPanel`
    - `AlarmEscalationPanel`
    - `AssistantPanel`
  - this did not block the login / registration chain, but it should be treated as frontend follow-up risk
- latest combined demo-facing regression run reported:
  - `37 passed`
  - command family included:
    - `tests/test_demo_e2e_flow.py`
    - `tests/test_care_auth_api.py`
    - `tests/test_health_api.py`
    - `tests/test_chat_api.py`
    - `tests/test_alarm_service.py`
- `TE-021` demo end-to-end API flow coverage has been completed and removed from the open gap board
- `TE-006` has been completed through lightweight repro coverage plus frontend registration-flow wiring regression coverage
- chat/API coverage follows the minimized public agent contract
- OM-line coverage now includes:
  - offline runtime regression
  - local model selection regression
  - prompt and KB integrity checks
- gateway HTTP prep coverage now includes:
  - candidate HTTP gateway fixtures in `tests/fixtures/gateway_http/`
  - parser-side dry-run checks in `tests/test_gateway_http_fixture_assets.py`
  - execution planning in `docs/gateway-http-parser-test-plan.md`
- demo-flow prep now includes:
  - end-to-end execution blueprint in `docs/demo-e2e-test-plan.md`

## Confirmed agent cautions

### 1. Public agent response shape should stay minimal

- public response shape is intended to be:
  - `answer`
  - `analysis`
  - `references`
- community response normalization preserves:
  - `risk_distribution`
  - `priority_devices`
  - `device_count`

Do not reintroduce `scope`, `mode`, or `network_online` as required frontend contract fields unless backend, tests, and docs are updated together.

### 2. Ollama HTTP fallback must stay aligned with the main local path

- fallback now uses explicit system/user message separation
- if prompt packaging changes again, verify both `ChatOllama` and raw HTTP fallback still enforce the same constraints

### 3. Device health report generation now exists as a public agent capability

- `POST /api/v1/chat/report/device` now generates a stable device health report for a requested time window
- report output is sanitized and structured for direct frontend consumption
- this is the chosen dedicated report contract; do not route report generation through `/chat/analyze` or `/chat/analyze/device`
- report shape includes:
  - `report_type`
  - `device_mac`
  - `period`
  - `summary`
  - `risk_level`
  - `risk_flags`
  - `key_findings`
  - `recommendations`
  - `metrics`
  - `references`

Follow-up caution:

- if frontend starts rendering this report, keep it on the structured fields only
- do not add raw model text passthrough around the report summary or sections

### 4. Dialogue model and report model now need to be truly separated

- product-side display must separate:
  - ordinary dialogue
  - formal health report
- internal routing is now allowed to add a dedicated report-model config / policy
- target behavior is:
  - dialogue path stays optimized for concise Q&A
  - formal report path calls health-model outputs and generates a normalized report
- keep public report schema stable unless FE / TE / AG are explicitly coordinated

## Remaining open work

Check the current task board for the live source of truth.

At the time of this handoff:

- `OM-*` work has been completed and removed from the open gap board
- `AG-*` first-stage report capability work is also functionally available on the backend
- `TE-021` has been completed and removed from the open gap board
- backend smoke for the demo runtime has been completed once successfully, but local runtime availability should still be rechecked before live demo use
- remaining open work now mainly lives in `FE-*`, blocked `TE-*`, and `BE-*` database hardening items
