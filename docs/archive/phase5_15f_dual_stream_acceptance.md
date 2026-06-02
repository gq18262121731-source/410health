# Phase 5.15F Dual Stream Runtime Long-run Acceptance

## Scope

Phase 5.15F validates the complete dual-stream runtime after Phase 5.15C/D/E:

- `main_stream` (`/tcp/av0_0`) is used for WebRTC display.
- `analysis_stream` (`/tcp/av0_1`) is used for AI analysis.
- Overlay coordinates from the analysis frame are mapped onto the displayed main stream.

This phase did not add features or modify AI algorithms, Temporal rules, frontend behavior beyond the existing mapping, GRU/LSTM, POST, snapshot, or alarm logic.

## Test Configuration

```text
ENABLE_DUAL_STREAM=true
MAIN_STREAM_URL=rtsp://admin:***@192.168.8.248:10554/tcp/av0_0
ANALYSIS_STREAM_URL=rtsp://admin:***@192.168.8.248:10554/tcp/av0_1
MAIN_CAPTURE_BACKEND=subprocess_opencv
ANALYSIS_CAPTURE_BACKEND=subprocess_opencv
ENABLE_TRACKING=true
ENABLE_IDENTITY_BINDING=true
IDENTITY_BINDING_ASYNC=true
ENABLE_POSE=true
ENABLE_BEHAVIOR=true
ENABLE_TEMPORAL=true
```

## 15-minute Result

Log:

```text
logs/runtime_debug/phase5_15f_dual_stream_long_run_15min.json
```

Summary:

```text
duration_sec: 900.67
sample_count: 900
status_failures: 0

main_connected_ratio: 100%
main_max_frame_age_ms: 219
main_frame_age > 3000ms: 0
main_restart_delta: 0

analysis_connected_ratio: 100%
analysis_max_frame_age_ms: 141
analysis_frame_age > 3000ms: 0
analysis_restart_delta: 0

tracking_worker_fps avg/min: 10.776 / 10.73
result_publish_fps avg/min: 9.235 / 9.20
detection_worker_fps avg: 4.615

pose_fps avg: 0.052
pose_latency_max_ms: 32
pose_skipped_due_to_busy_delta: 0
pose_circuit_open_seen: false

pipeline_errors: 0
temporal_errors: 0
gpu_util avg/max: 19.544% / 24%
gpu_memory max: 1575 MB
vision_memory_delta_mb: -1.69
identity_memory_delta_mb: -2.09
```

15-minute acceptance passed.

## 30-minute Result

Log:

```text
logs/runtime_debug/phase5_15f_dual_stream_long_run.json
```

Summary:

```text
duration_sec: 1812.8
sample_count: 1800
status_failures: 0

main_connected_ratio: 99.94%
main_max_frame_age_ms: 2953
main_frame_age > 3000ms: 0
main_restart_delta: 1

analysis_connected_ratio: 99.83%
analysis_max_frame_age_ms: 4156
analysis_frame_age > 3000ms: 2
analysis_restart_delta: 1

tracking_worker_fps avg/min: 10.699 / 7.80
result_publish_fps avg/min: 9.174 / 7.21
detection_worker_fps avg: 4.463

pose_fps avg: 0.188
pose_latency_max_ms: 312
pose_skipped_due_to_busy_delta: 25
pose_circuit_open_seen: false

pipeline_errors: 0
temporal_errors: 0
gpu_util avg/max: 8.964% / 28%
gpu_memory max: 1853 MB
webrtc_clients_max: 1
ws_clients_max: 1
```

The 30-minute test passed the core runtime criteria. The analysis stream had two short stale windows over `3000ms`, with one subprocess restart, and recovered without affecting service availability or AI pipeline health.

## Frontend Observation

Observed via `/demo` after the 30-minute test:

```text
WebRTC: connected
WebSocket: connected
Stream: normal
Frame: 640x360 analysis frame metadata
display_source: main
analysis_source: analysis
main_stream: 1280x720
analysis_stream: 640x360
```

Visual observation:

- The displayed video is the main stream.
- Bbox and skeleton are rendered on the main stream with the new analysis-to-display coordinate mapping.
- Bbox and skeleton are basically aligned with the person.
- Fast movement can show slight lag, consistent with expected main/analysis stream timing differences.
- Browser console had no warnings or errors during the smoke check.

## Acceptance Decision

Phase 5.15F passes as a dual-stream runtime long-run acceptance.

The recommended competition/test default is now:

```text
ENABLE_DUAL_STREAM=true
MAIN_STREAM_URL=/tcp/av0_0
ANALYSIS_STREAM_URL=/tcp/av0_1
MAIN_CAPTURE_BACKEND=subprocess_opencv
ANALYSIS_CAPTURE_BACKEND=subprocess_opencv
```

## Remaining Boundaries

- The dual-stream runtime still has no fallback logic in this phase.
- `analysis_stream` had two short `frame_age > 3000ms` events in the 30-minute run, but recovered.
- Overlay can have slight lag during fast motion because main and analysis streams are not frame-synchronized.
- If the camera's main/sub stream FOV ever differs, simple coordinate scaling will not be sufficient.

## Next Recommendation

Proceed to fallback only if needed:

- Main stream down: display should optionally fall back to analysis stream.
- Analysis stream down: main display should continue, while AI status becomes unavailable.

Fallback is useful but not mandatory for the current competition/test default because the core dual-stream runtime is now stable enough for staged testing.
