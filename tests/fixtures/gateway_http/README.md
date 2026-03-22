# Gateway HTTP Fixture Prep

These files are test-owned preparation assets for `TE-019`.

They are intentionally **not** the final backend HTTP contract.
`BE-013` is still responsible for locking the real gateway receiver API.

Current purpose:

- keep a stable set of candidate gateway request bodies
- ensure every candidate body already contains a top-level `devices[]`
- keep vendor-style raw payload examples that the current parser stack can already understand
- let test work start before the HTTP receiver endpoint and real hardware arrive

Current assumptions:

- future HTTP uploads are expected to use MessagePack on the wire
- these JSON files are the canonical human-readable source fixtures
- once `BE-013` lands, these bodies can be serialized into MessagePack without rewriting the sample data

Current parser-side dry-run path:

1. read `body.devices[*].raw_payload`
2. hand it to `MQTTGatewayListener.build_sample(...)`
3. rely on the existing listener + parser stack to validate sample extraction behavior

Why the MQTT listener is reused here:

- it already understands the vendor raw gateway payload shape
- it already normalizes `data_type`, `device_mac`, `rssi`, and raw BLE payload
- it lets test preparation stay close to the future HTTP gateway handoff without inventing new parsing logic
