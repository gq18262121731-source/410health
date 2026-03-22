# Collaboration Gap Task Board

Last updated: 2026-03-22
Source of truth for rules: `docs/agent-collaboration-contract.md`

## Maintenance Rules

- This file contains unresolved work only.
- Remove a task after code, tests, and docs are aligned.
- Do not keep completed items here for history.
- Prefer ASCII task IDs and stable titles to reduce encoding risk.
- When terminal output and browser output disagree on Chinese text quality, treat the browser and UTF-8 source files as the source of truth before editing content.

Status values:

- `OPEN`
- `IN_PROGRESS`
- `BLOCKED`

## Role And Prefix Rules

- `FE-xxx`: Frontend Engineer
- `UI-xxx`: UI Designer
- `BE-xxx`: Backend Engineer
- `TE-xxx`: Test Engineer
- `DR-xxx`: Device Registration Engineer
- `AG-xxx`: Agent Engineer
- `OM-xxx`: Offline Model Engineer
- `HM-xxx`: Health Model Engineer

Role boundaries:

- `FE-`: UI wiring, presentation logic, operator-facing states, live page integration
- `UI-`: visual direction, design system, layout quality, typography, color, interaction polish
- `BE-`: product/API policy, auth, contract, general backend behavior, persistence hardening
- `TE-`: regression coverage, validation coverage, scenario coverage
- `DR-`: device registration, binding, lifecycle, ledger, audit, persistence
- `AG-`: agent protocol, response normalization, tool orchestration, report generation contract, agent-test alignment
- `OM-`: local-model policy, Qwen/Deepseek routing, prompt package, local RAG, knowledge base
- `HM-`: health scoring, anomaly detection, transformer time-series model, prioritization, calibration, health-model regression

## Current Demo Priority

### Wave 1: separate dialogue and report model flow

- `OM-010` Separate local dialogue-model and report-model routing policy.
- `HM-008` Expose normalized health-model report context for dedicated report generation.
- `AG-004` Route formal report generation through the dedicated report-model path while keeping the public report schema stable.
- `BE-023` Add backend config and internal routing support for a dedicated local report model.
- `FE-014` Split AI dialogue and health report into different frontend entry points and rendering areas.
- `TE-022` Verify separated dialogue/report routing behavior and frontend presentation split.

### Wave 2: login/register chain stabilization

- `FE-011` Keep the approved login redesign stable in the real frontend.
- `FE-012` Keep the animated ECG login background stable with graceful mobile fallback.

### Wave 3: extend the approved visual baseline across the website

- `UI-005` Community overview redesign.
- `UI-006` Member-and-device redesign.
- `UI-007` Alert / queue / report / trend redesign.
- `FE-013` Extract shared visual primitives and apply the approved baseline across business pages.

### Wave 4: database hardening after demo flow is stable

- `BE-016`
- `BE-017`
- `BE-018`
- `BE-019`
- `BE-020`

### Wave 5: gateway implementation after core demo pages are stable

- `BE-021`
- `BE-022`

### Still blocked

- `TE-020`

## Frontend Engineer

### FE-011 Implement and stabilize the approved login redesign

- Status: `IN_PROGRESS`
- Owner: `frontend`
- Required change:
  - Keep the current login chain stable in the real frontend.
  - Split the auth flow into smaller page-like steps instead of one oversized screen.
  - Use interaction-driven navigation between:
    - login
    - identity selection
    - register account
    - complete profile
    - completion state
  - Make the background fill the viewport and adapt to different screen ratios.
  - Use `src/assets/bg.jpg` as the current base image unless the user explicitly changes it.
  - Keep the real formal login flow working.
  - Follow the approved login-card size rules from `docs/login-card-size-spec-zh.md`.

### FE-012 Keep the animated ECG login background stable

- Status: `IN_PROGRESS`
- Owner: `frontend`
- Required change:
  - Implement the login-page animated background according to `docs/login-animated-background-spec.md`.
  - Prefer:
    - SVG ECG line
    - gradient sweep
    - optional light particles only if needed
  - Keep the background visually behind the card instead of washing out the whole page.
  - Provide a lighter mobile fallback.

### FE-013 Extract shared visual primitives for full-site consistency

- Status: `OPEN`
- Owner: `frontend`
- Required change:
  - Extract reusable visual primitives from the approved login-page baseline.
  - Standardize:
    - card shells
    - buttons
    - input fields
    - chips / pills
    - feedback banners
    - empty / loading / error blocks
  - Apply them gradually across business pages without changing backend contracts.

### FE-014 Split dialogue and report presentation in the frontend

- Status: `OPEN`
- Owner: `frontend`
- Required change:
  - Separate ordinary AI dialogue and formal health-report generation into different entry points.
  - Separate ordinary AI dialogue and formal health reports into different rendering containers and user-facing labels.
  - Keep report generation on `POST /api/v1/chat/report/device`.
  - Do not present the formal report inside the same UI block used for ordinary chat answers.
  - Prepare the frontend so a dedicated report-model route can be adopted without changing the public report schema.

## UI Designer

### UI-005 Community overview redesign

- Status: `OPEN`
- Owner: `ui`
- Required change:
  - Redesign the community overview page using the approved login-page visual baseline.
  - Clarify KPI cards, risk distribution, priority list, and daily activity hierarchy.
  - Keep the approved green-led, light-glass visual language.

### UI-006 Member-and-device redesign

- Status: `OPEN`
- Owner: `ui`
- Required change:
  - Replace the unclear `关系台账` concept with the clearer product-facing page concept `成员与设备`.
  - Redesign the member/device page so people understand:
    - who the elder is
    - who the family member is
    - which device is bound
    - what actions are available
  - Keep the existing operator flow and backend contract unchanged.

### UI-007 Alert / queue / report / trend redesign

- Status: `OPEN`
- Owner: `ui`
- Required change:
  - Redesign alert list, alert queue, alert details, report sections, and trend presentation using the approved baseline.
  - Make alert level, alert stage, follow-up actions, and report hierarchy visually obvious.

## Backend Engineer

### BE-016 Persist formal user registration

- Status: `OPEN`
- Owner: `backend`
- Required change:
  - Persist elder / family / community-staff registration records in the runtime database.
  - Move formal login lookup and uniqueness checks off pure in-memory state.
  - Keep restart behavior stable for demo registration flow.

### BE-017 Persist elder-family relations

- Status: `OPEN`
- Owner: `backend`
- Required change:
  - Persist elder-family bindings in the runtime database.
  - Keep relation lookup and primary-relation behavior stable across restart.
  - Align directory and access-profile data with persisted relation state.

### BE-018 Persist health time-series samples

- Status: `OPEN`
- Owner: `backend`
- Required change:
  - Add a durable storage path for ingested health samples.
  - Keep realtime cache for live display, but make trend/report inputs restart-safe.
  - Prefer the existing database schema direction instead of keeping health history memory-only.

### BE-019 Persist alarm history and acknowledge state

- Status: `OPEN`
- Owner: `backend`
- Required change:
  - Persist generated alarms and acknowledge state.
  - Keep active-alarm and historical-alarm lookup stable across restart.
  - Support demo alarm flow without losing state on backend restart.

### BE-020 Add gateway quarantine and audit persistence

- Status: `OPEN`
- Owner: `backend`
- Required change:
  - Add durable storage for BLE gateway request-level metadata and per-device intake results.
  - Persist quarantine / pending-registration evidence for unregistered devices.
  - Keep mixed-batch intake results traceable without polluting the normal health flow.

### BE-021 Implement BLE HTTP receiver endpoint and MessagePack decoding

- Status: `OPEN`
- Owner: `backend`
- Required change:
  - Implement the actual BLE gateway HTTP endpoint.
  - Accept MessagePack request bodies according to `docs/ble-gateway-http-contract.md`.
  - Decode `devices[]` frames and hand registered devices into the existing parser -> ingest path.
  - Do not auto-register unregistered devices.

### BE-022 Persist gateway metadata and quarantine records

- Status: `OPEN`
- Owner: `backend`
- Required change:
  - Persist request-level gateway metadata and per-device intake outcomes.
  - Persist quarantine / pending-registration evidence for unregistered devices.
  - Keep the runtime behavior aligned with `docs/ble-gateway-http-prep.md`.

### BE-023 Add dedicated report-model config and internal routing support

- Status: `OPEN`
- Owner: `backend`
- Required change:
  - Allow a dedicated internal report-model configuration instead of only `local_default_model` and `local_reasoning_model`.
  - Support internal routing separation between:
    - ordinary dialogue
    - formal health report generation
  - Keep public API fields and the formal report schema unchanged unless explicitly coordinated.

## Device Registration Engineer

No open `DR-*` tasks right now.

## Offline Model Engineer

### OM-010 Separate local dialogue-model and report-model routing policy

- Status: `OPEN`
- Owner: `offline-model`
- Required change:
  - Add a dedicated internal report-model routing policy instead of keeping dialogue and report on the same `_select_local_model(...)` path.
  - Introduce a dedicated report-model configuration entry such as `local_report_model` or equivalent internal routing policy.
  - Keep ordinary dialogue output limits on the dialogue path only.
  - Keep the public report schema unchanged.

## Agent Engineer

### AG-004 Use the dedicated report-model path for formal report generation

- Status: `OPEN`
- Owner: `agent`
- Required change:
  - Switch formal report generation onto the dedicated report-model route once backend/config support exists.
  - Keep ordinary dialogue behavior unchanged.
  - Keep the public report contract stable for frontend consumption.
  - Preserve response sanitization so prompt/tool/internal fields stay hidden.

## Health Model Engineer

### HM-008 Provide normalized health-model report context

- Status: `OPEN`
- Owner: `health-model`
- Required change:
  - Expose a stable internal health-model context for formal report generation.
  - Ensure the dedicated report-model path can call health-model outputs directly.
  - Provide normalized inputs for:
    - risk score
    - anomaly explanation
    - sustained-abnormality status
    - alarm-readiness
  - Avoid breaking the public report schema unless explicitly coordinated.

## Test Engineer

### TE-022 Verify dialogue/report separation behavior

- Status: `OPEN`
- Owner: `test`
- Required change:
  - Verify that ordinary dialogue and formal health reports use separate product surfaces in the frontend.
  - Verify that formal reports continue to use `POST /api/v1/chat/report/device`.
  - Verify that ordinary dialogue output limits do not truncate the formal report path.
  - Verify that the public report schema remains unchanged after routing separation.

### TE-020 Gateway live integration test

- Status: `BLOCKED`
- Owner: `test`
- Required change:
  - Run live integration verification only after hardware, receiver endpoint, MessagePack decoding, and parser handoff all exist.
