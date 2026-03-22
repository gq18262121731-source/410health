# Gateway HTTP Parser Test Plan

Last updated: 2026-03-21
Related tasks:

- `TE-019`
- `TE-020`
- `DR-006`
- `DR-007`
- `BE-013`

## Goal

Prepare test-owned assets so the team can move directly into gateway HTTP verification once the receiver endpoint and hardware are available.

## Not In Scope Yet

- no live hardware verification
- no real HTTP receiver endpoint assertions
- no final MessagePack decoder verification against a production handler

Those belong to `TE-020` after the backend receiver path exists.

## Assets Prepared Now

- candidate fixtures:
  - `tests/fixtures/gateway_http/gateway_http_broadcast_devices_array.json`
  - `tests/fixtures/gateway_http/gateway_http_response_merge_devices_array.json`
  - `tests/fixtures/gateway_http/gateway_http_malformed_devices_array.json`
- parser-side dry-run regression:
  - `tests/test_gateway_http_fixture_assets.py`

These fixture files are the canonical human-readable source fixtures for a future MessagePack HTTP body.

## Current Assumptions

- future gateway HTTP uploads will use MessagePack
- the body will include top-level gateway metadata plus `devices[]`
- each `devices[]` item will carry a vendor-style raw BLE payload or an equivalent parser-ready field
- current parser dry-run uses `MQTTGatewayListener.build_sample(...)` because that is the existing adapter that already understands the vendor raw gateway payload format

## Planned Verification Stages

### Stage 1. HTTP body acceptance

Verify once `BE-013` lands:

1. receiver accepts `Content-Type: application/msgpack`
2. MessagePack body decodes into the expected top-level structure
3. malformed MessagePack returns a stable client error
4. missing `devices[]` or empty `devices[]` returns a stable validation error

### Stage 2. Parser handoff

For each `devices[]` entry:

1. extract raw payload
2. normalize MAC and RSSI fields if provided
3. route the raw payload into parser-side handling
4. verify expected outcomes:
   - broadcast -> `packet_type = broadcast`
   - response A -> `packet_type = response_a`
   - response A + response B pair -> merged `packet_type = response_ab`
   - malformed raw payload -> no sample or explicit rejection path, depending on final endpoint contract

### Stage 3. Registered-device state transition

Once the HTTP receiver writes through to ingest:

1. register a device through `/api/v1/devices/register`
2. send a gateway HTTP upload for that MAC
3. verify:
   - `/api/v1/health/realtime/{mac}` updates
   - `/api/v1/health/trend/{mac}` contains the new sample
   - device remains `offline` before ingest and becomes observable after ingest

### Stage 4. Unregistered-device policy

Blocked on `DR-007`.

After the policy is defined, verify one of:

- upload is rejected for unknown MAC in formal mode
- upload is accepted but quarantined or logged
- upload auto-creates only in a deliberately documented mode

### Stage 5. Alarm side effects

Send abnormal gateway uploads and verify:

1. critical broadcast or merged response values create alarm records
2. `/api/v1/alarms`
3. `/api/v1/alarms/queue`
4. `/api/v1/alarms/mobile-pushes`

all reflect the expected side effects.

## Fixture Matrix

### Broadcast fixture

- file:
  - `tests/fixtures/gateway_http/gateway_http_broadcast_devices_array.json`
- covers:
  - top-level `devices[]`
  - vendor raw payload parsing
  - broadcast packet extraction

### Response merge fixture

- file:
  - `tests/fixtures/gateway_http/gateway_http_response_merge_devices_array.json`
- covers:
  - ordered multi-entry `devices[]`
  - response A then response B merge
  - final `response_ab` output

### Malformed fixture

- file:
  - `tests/fixtures/gateway_http/gateway_http_malformed_devices_array.json`
- covers:
  - parser-safe rejection path
  - future HTTP validation negative case

## Immediate Next Step After Endpoint Lands

1. duplicate the parser-side fixture coverage into a real HTTP API test file
2. serialize the current fixture bodies to MessagePack in the request layer
3. assert the receiver response body and status code
4. reuse the same candidate data before touching hardware

## Hardware-Day Cutover Checklist

1. confirm receiver path exists
2. confirm MessagePack decode exists
3. confirm raw payload is handed into parser
4. confirm the hardware sends the same vendor payload semantics assumed by the fixtures
5. only then run `TE-020`
