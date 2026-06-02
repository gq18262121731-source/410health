# Phase 5.15A Dual Stream Feasibility Report

## Scope

This phase only validates whether the camera and the current machine can pull two RTSP streams at the same time:

- Main/display stream: `/tcp/av0_0`
- Analysis stream: `/tcp/av0_1`

No business pipeline was changed. This test does not connect the streams to WebRTC, DetectionWorker, TrackingWorker, PoseWorker, TemporalService, ResultPublisher, frontend overlay, GRU, POST, snapshot, or alarm logic.

## Test Method

Added script:

```text
scripts/debug_dual_stream_feasibility.py
```

The script starts two independent `SubprocessCaptureWorker` instances:

```text
dual_main     -> rtsp://admin:***@192.168.8.248:10554/tcp/av0_0
dual_analysis -> rtsp://admin:***@192.168.8.248:10554/tcp/av0_1
```

Both streams use the existing subprocess OpenCV capture backend and isolated `FrameBuffer` instances. The test records only capture/runtime health.

Output:

```text
logs/runtime_debug/dual_stream_feasibility.json
```

## 30-Second Smoke Result

```text
main connected_ratio: 90.00%
analysis connected_ratio: 93.33%
main max_frame_age_ms: 110ms
analysis max_frame_age_ms: 110ms
main avg_capture_fps: 8.28
analysis avg_capture_fps: 8.68
main restart_delta: 0
analysis restart_delta: 0
main output: 1280x720
analysis output: 640x360
```

The lower connected ratio in the smoke test is caused by startup warm-up time.

## 10-Minute Feasibility Result

```text
duration_sec: 600
sample_count: 600

main connected_ratio: 99.67%
analysis connected_ratio: 99.67%

main frame_age > 3000ms: 0
analysis frame_age > 3000ms: 0

main max_frame_age_ms: 360ms
analysis max_frame_age_ms: 110ms

main avg_capture_fps: 9.18
analysis avg_capture_fps: 9.24

main restart_delta: 0
analysis restart_delta: 0

main ipc_decode_error_delta: 0
analysis ipc_decode_error_delta: 0

main final_output: 1280x720
analysis final_output: 640x360

gpu_util_avg: 18.25%
gpu_memory_max_mb: 1330MB
process_memory_delta_mb: +7.24MB
```

The terminal messages at the end:

```text
capture process stream closed
manual_stop
```

were produced by the script stopping both workers after the test. They are not runtime failures.

## Findings

1. The camera can provide `/tcp/av0_0` and `/tcp/av0_1` concurrently.
2. Pulling the main stream did not destabilize the analysis stream during this 10-minute test.
3. The analysis stream stayed stable with no `frame_age > 3000ms` events.
4. The main stream did not show frequent `stream closed` or restart behavior in this isolated test.
5. CPU/GPU overhead is visible but acceptable for capture-only feasibility.

## Feasibility Decision

Dual-stream architecture is feasible on this camera and current machine under capture-only conditions.

Recommended next design direction remains:

```text
main / av0_0     -> WebRTC display
analysis / av0_1 -> AI pipeline
```

## Boundaries

- This does not prove the full dual-stream business architecture is complete.
- This does not include WebRTC encoding of the main stream.
- This does not include AI running on the analysis stream at the same time.
- This does not include overlay coordinate mapping.
- This does not change Temporal rules or fall preview behavior.

## Next Step

If we proceed, the next phase should be a separate design/implementation task for dual-stream integration:

1. Add explicit `main_stream` and `analysis_stream` runtime slots.
2. Keep AI workers consuming only `analysis_stream`.
3. Keep WebRTC consuming `main_stream`, with fallback to `analysis_stream`.
4. Add result payload metadata for analysis frame size.
5. Map overlay coordinates from analysis dimensions to display dimensions.
