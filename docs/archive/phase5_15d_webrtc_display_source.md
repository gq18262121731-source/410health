# Phase 5.15D WebRTC Display Source Switch

## Scope

Phase 5.15D only changes the WebRTC video source selection.

Implemented:

- Single-stream mode keeps the original WebRTC behavior.
- Dual-stream mode makes WebRTC read `main_frame_buffer`.
- AI workers continue reading `analysis_frame_buffer`.
- `/status` exposes `display_source` and `analysis_source`.

Not implemented:

- frontend overlay coordinate mapping
- ResultPublisher payload metadata changes
- fallback from main to analysis
- Temporal rule changes
- Pose logic changes
- Detection logic changes
- GRU/LSTM
- POST/snapshot/alarm logic

## WebRTC Source

Single stream:

```text
WebRTC -> runtime.frame_buffer
display_source = single
analysis_source = single
```

Dual stream:

```text
WebRTC -> runtime.main_frame_buffer
display_source = main

AI pipeline -> runtime.analysis_frame_buffer
analysis_source = analysis
```

## Files Changed

```text
app/camera/source_manager.py
app/streaming/peer_manager.py
app/schemas/status.py
app/services/status_service.py
```

## Validation

### Single-Stream Compatibility

Configuration:

```text
ENABLE_DUAL_STREAM=false
DEFAULT_RTSP_URL=.../tcp/av0_1
```

Result:

```text
display_source: single
analysis_source: single
main_stream: connected
analysis_stream: connected
main width: 640
analysis width: 640
tracking_worker_fps: 10.83
result_publish_fps: 9.29
pipeline.last_error: null
```

### Dual-Stream Startup

Configuration:

```text
ENABLE_DUAL_STREAM=true
MAIN_STREAM_URL=.../tcp/av0_0
ANALYSIS_STREAM_URL=.../tcp/av0_1
```

Result after clean restart:

```text
display_source: main
analysis_source: analysis
main_stream: connected
analysis_stream: connected
main width: 1280
analysis width: 640
tracking_worker_fps: 10.74
result_publish_fps: 9.21
pipeline.last_error: null
```

### 10-Minute Runtime

Output:

```text
logs/runtime_debug/phase5_15d_webrtc_display_source.json
```

Summary:

```text
duration_sec: 600
sample_count: 600
status_failures: 0

display_source_final: main
analysis_source_final: analysis

main connected_ratio: 98.50%
main frame_age > 3000ms: 8
main max_frame_age_ms: 10282ms
main avg_capture_fps: 9.04
main restart_delta: 1
main final_state: connected

analysis connected_ratio: 100%
analysis frame_age > 3000ms: 0
analysis max_frame_age_ms: 1062ms
analysis avg_capture_fps: 9.07
analysis restart_delta: 0
analysis final_state: connected

tracking_worker_fps avg/min: 10.77 / 10.71
result_publish_fps avg/min: 9.23 / 9.19
pipeline_errors: 0
```

## Decision

Phase 5.15D passes its scoped goal:

```text
WebRTC now reads main_frame_buffer in dual-stream mode.
AI remains on analysis_frame_buffer.
```

The main stream still had one reconnect/stale window during the 10-minute run. This did not affect the analysis stream or AI pipeline.

## Next Step

Recommended next phase:

```text
Phase 5.15E: Overlay Coordinate Mapping
```

That phase should add result metadata and frontend mapping from analysis coordinates to the displayed main stream.

Fallback should remain a separate later phase.
