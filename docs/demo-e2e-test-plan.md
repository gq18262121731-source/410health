# Demo E2E Test Plan

Last updated: 2026-03-21
Related task:

- `TE-021`

## Goal

Prepare the end-to-end demo verification path now, without waiting for live gateway hardware.

This plan is meant to prove the demo chain below in a repeatable order:

1. register device
2. see realtime data
3. trigger abnormal state
4. generate time-window report
5. observe alarm after sustained abnormal duration

## Current API Anchors

The current backend already exposes enough API surface to dry-run most of the chain:

- register device:
  - `POST /api/v1/devices/register`
- ingest health sample:
  - `POST /api/v1/health/ingest`
- read realtime sample:
  - `GET /api/v1/health/realtime/{device_mac}`
- read intelligent analysis:
  - `GET /api/v1/health/intelligent/{device_mac}`
- read alarms:
  - `GET /api/v1/alarms`
  - `GET /api/v1/alarms/queue`
- generate report:
  - `POST /api/v1/chat/report/device`

## What Is Already Covered By Regression

- device registration and ownership lifecycle:
  - `tests/test_registration_flow_api.py`
- parser and vendor raw payload handling:
  - `tests/test_parser.py`
  - `tests/test_mqtt_listener.py`
  - `tests/test_gateway_http_fixture_assets.py`
- realtime and intelligent health endpoints:
  - `tests/test_health_api.py`
- device report generation:
  - `tests/test_chat_api.py`
- sustained abnormal -> intelligent alarm progression:
  - `tests/test_alarm_service.py`

## Planned Demo Verification Layers

### Layer 1. API-only dry run

This can run before hardware arrives.

1. create or log in as a management-capable user
2. register an elder and a device
3. inject normal samples through `/api/v1/health/ingest`
4. verify realtime and trend endpoints populate
5. inject worsening samples
6. verify intelligent analysis starts returning a meaningful result
7. verify alarm queue reflects escalated sustained abnormality
8. generate a time-window report and verify stable report fields

### Layer 2. Demo-script alignment

Use `docs/demo-script.md` plus this plan to make sure the live demo tells the same story as the APIs:

- normal baseline
- abnormal drift
- sustained abnormal escalation
- alarm visibility
- report generation and explanation

### Layer 3. Hardware-assisted run

Blocked until `TE-020`.

Replace `/health/ingest` stand-in steps with the future HTTP gateway receiver or real gateway hardware path.

## Proposed Dry-Run Scenario

### Scenario A. Registered device becomes visible in realtime

1. register device for a formal elder
2. post a normal sample through `/health/ingest`
3. assert:
   - `/health/realtime/{mac}` returns `200`
   - `/health/trend/{mac}` contains the new sample

### Scenario B. Abnormality emerges

1. continue posting a short sequence with:
   - rising temperature
   - falling blood oxygen
   - rising heart rate
2. assert:
   - `/health/intelligent/{mac}` returns `ready = true`
   - report generation shows non-empty `risk_level`, `key_findings`, and `recommendations`

### Scenario C. Sustained abnormality escalates to alarm

1. use the reproducible sustained anomaly pattern already represented in `tests/test_alarm_service.py`
2. feed the sequence through ingest
3. assert:
   - `/alarms`
   - `/alarms/queue`
   - mobile push list if relevant to the demo

all reflect the alarmed state

### Scenario D. Time-window report

1. call `POST /api/v1/chat/report/device` for the abnormal window
2. assert:
   - `report_type`
   - `period.sample_count`
   - `summary`
   - `risk_level`
   - `key_findings`
   - `recommendations`
   - `metrics`
   - `references`

are all present and stable

## What Is Still Blocked

- final frontend demo presentation for:
  - evaluation score placement
  - report rendering flow
  - anomaly-to-alarm visualization
- live gateway hardware and HTTP receiver integration
- any UI-only assertions that depend on FE demo flows rather than backend APIs

## Suggested Automation Split

### Can be automated now

- API registration
- ingest-driven realtime update
- abnormal sequence injection
- alarm assertions
- report-generation assertions

### Should wait for FE demo stabilization

- browser-level end-to-end walkthroughs
- dashboard timing assertions
- exact presentation sequencing for demo visuals

### Should wait for hardware

- real gateway upload path
- real BLE packet capture from device hardware

## Exit Criteria For Future TE-021 Execution

TE-021 should be considered fully executed once one repeatable path proves all of the following in the same run:

1. device is registered
2. realtime sample becomes visible
3. abnormality becomes visible
4. sustained abnormality creates alarm state
5. time-window report is generated and render-ready
