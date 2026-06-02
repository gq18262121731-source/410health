# Phase 5.15C Dual Runtime Foundation

## Scope

Phase 5.15C implements the dual-stream runtime foundation only.

Implemented:

- dual capture runtime
- dual `FrameBuffer`
- `main_stream` and `analysis_stream` status
- dual-stream configuration
- single-stream compatibility
- AI workers continue reading the analysis stream

Not implemented in this phase:

- WebRTC source switch to main stream
- frontend overlay coordinate mapping
- ResultPublisher payload metadata
- fallback behavior
- Temporal rule changes
- Pose logic changes
- alert/POST/snapshot/GRU

## Runtime Model

Single-stream mode:

```text
ENABLE_DUAL_STREAM=false

runtime.frame_buffer          -> existing single buffer
runtime.main_frame_buffer     -> same buffer
runtime.analysis_frame_buffer -> same buffer
runtime.worker                -> existing single worker
runtime.main_worker           -> same worker
runtime.analysis_worker       -> same worker
```

Dual-stream mode:

```text
ENABLE_DUAL_STREAM=true

main_stream     -> MAIN_STREAM_URL     -> main_capture_worker     -> main_frame_buffer
analysis_stream -> ANALYSIS_STREAM_URL -> analysis_capture_worker -> analysis_frame_buffer
```

Compatibility:

```text
runtime.frame_buffer and source_manager.get_buffer() still point to analysis_frame_buffer.
```

This keeps existing downstream consumers compatible while making the analysis stream explicit.

## AI Input

The AI path reads only the analysis stream:

```text
DetectionWorker -> source_manager.get_analysis_buffer(camera_id)
PoseWorker      -> source_manager.get_analysis_buffer(camera_id)
IdentityWorker  -> source_manager.get_analysis_buffer(camera_id)
```

Tracking, Behavior, Temporal, and ResultPublisher continue consuming the existing realtime pipeline outputs.

## WebRTC Boundary

This phase does not switch WebRTC to the main stream.

Current behavior:

```text
WebRTC still reads runtime.frame_buffer.
runtime.frame_buffer currently maps to analysis_frame_buffer.
```

The main stream is captured and exposed in status, but it is not yet used as the WebRTC video source.

## Status Fields

`/status` now includes:

```json
{
  "main_stream": {
    "enabled": true,
    "source_url_masked": "rtsp://admin:***@192.168.8.248:10554/tcp/av0_0",
    "stream_state": "connected",
    "connected": true,
    "frame_width": 1280,
    "frame_height": 720,
    "frame_age_ms": 40,
    "capture_fps": 9.2,
    "capture_backend": "subprocess_opencv",
    "restart_count": 0,
    "last_error": null
  },
  "analysis_stream": {
    "enabled": true,
    "source_url_masked": "rtsp://admin:***@192.168.8.248:10554/tcp/av0_1",
    "stream_state": "connected",
    "connected": true,
    "frame_width": 640,
    "frame_height": 360,
    "frame_age_ms": 30,
    "capture_fps": 9.2,
    "capture_backend": "subprocess_opencv",
    "restart_count": 0,
    "last_error": null
  }
}
```

Legacy compatibility:

```text
/status.cameras[0] is preserved and currently maps to the analysis stream.
```

## Configuration

Added:

```text
ENABLE_DUAL_STREAM=false
MAIN_STREAM_URL=
ANALYSIS_STREAM_URL=
MAIN_CAPTURE_BACKEND=subprocess_opencv
ANALYSIS_CAPTURE_BACKEND=subprocess_opencv
```

Dual-stream test configuration:

```text
ENABLE_DUAL_STREAM=true
MAIN_STREAM_URL=rtsp://admin:***@192.168.8.248:10554/tcp/av0_0
ANALYSIS_STREAM_URL=rtsp://admin:***@192.168.8.248:10554/tcp/av0_1
MAIN_CAPTURE_BACKEND=subprocess_opencv
ANALYSIS_CAPTURE_BACKEND=subprocess_opencv
```

## Validation

### Case 1: Single-Stream Compatibility

Configuration:

```text
ENABLE_DUAL_STREAM=false
DEFAULT_RTSP_URL=rtsp://admin:***@192.168.8.248:10554/tcp/av0_1
```

Result:

```text
cameras[0].stream_state: connected
main_stream.stream_state: connected
analysis_stream.stream_state: connected
main_stream.frame_width: 640
analysis_stream.frame_width: 640
capture_fps: 9.23
tracking_worker_fps: 10.77
result_publish_fps: 9.23
```

Single-stream behavior is preserved.

### Case 2: Dual-Stream Startup

Configuration:

```text
ENABLE_DUAL_STREAM=true
MAIN_STREAM_URL=.../tcp/av0_0
ANALYSIS_STREAM_URL=.../tcp/av0_1
```

Result:

```text
main_stream.stream_state: connected
analysis_stream.stream_state: connected
main_stream.frame_width/frame_height: 1280x720
analysis_stream.frame_width/frame_height: 640x360
main_stream.capture_fps: 9.22
analysis_stream.capture_fps: 9.22
tracking_worker_fps: 10.76
result_publish_fps: 9.22
pipeline.last_error: null
```

### Case 3: 10-Minute Long Run

Output:

```text
logs/runtime_debug/phase5_15c_dual_runtime.json
```

Summary:

```text
duration_sec: 600
sample_count: 600
status_failures: 0

main connected_ratio: 100%
analysis connected_ratio: 100%

main frame_age > 3000ms: 0
analysis frame_age > 3000ms: 0

main max_frame_age_ms: 1625ms
analysis max_frame_age_ms: 1531ms

main avg_capture_fps: 9.11
analysis avg_capture_fps: 9.15

main restart_delta: 0
analysis restart_delta: 0

tracking_worker_fps avg/min: 10.74 / 10.70
result_publish_fps avg/min: 9.21 / 9.16
pipeline_errors: 0
pose_fps_avg: 0.54
```

## Files Changed

```text
app/core/config.py
app/camera/source_models.py
app/camera/source_manager.py
app/services/detection_service.py
app/services/pose_worker_service.py
app/services/identity_binding_worker_service.py
app/services/status_service.py
app/schemas/status.py
.env.example
```

## Current Boundary

Phase 5.15C only establishes the dual runtime foundation.

The system now can run two capture streams and expose both statuses, but:

- WebRTC has not been switched to `main_stream`.
- Overlay coordinate mapping has not been implemented.
- Result payload metadata has not been added.
- Fallback behavior has not been implemented.

## Recommendation

Phase 5.15C passes.

Next phase should be:

```text
Phase 5.15D: WebRTC Display Source Switch
```

That phase should make WebRTC read `main_frame_buffer`, while keeping AI on `analysis_frame_buffer`.
