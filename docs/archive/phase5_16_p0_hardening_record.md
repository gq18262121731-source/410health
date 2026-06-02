# Phase 5.16 P0 Hardening Record

## Scope

Phase 5.16 addresses real-person test interruptions in the dual-stream runtime. This phase does not change fall rules, temporal logic, detection, pose models, GRU/LSTM, alerts, POST, or snapshots.

## Observed P0 Issues

- Video delay occasionally reached 10-15 seconds.
- Video corruption appeared during severe delay windows.
- WebRTC entered failed state and WebSocket closed.
- Backend streams later recovered, but the frontend did not automatically recover.
- Capture restart counts increased during the stall window.

## Changes

### Frontend auto recovery

- WebRTC reconnects automatically after `failed`, `disconnected`, or `closed`.
- WebSocket reconnects automatically after `closed` or `error`.
- Backoff uses 1s, 2s, then 5s.
- The page shows recovery messages:
  - `WebRTC 重连中`
  - `WebSocket 重连中`
  - `高清流恢复中`
  - `AI 分析流恢复中`
  - `高清流恢复中，已切换稳定分析流显示`

### Display fallback

- Runtime can fall back WebRTC display source from `main_stream` to `analysis_stream` when the main stream is not healthy.
- Fallback is controlled by:
  - `DISPLAY_FALLBACK_TO_ANALYSIS=true`
  - `DISPLAY_FALLBACK_FRAME_AGE_MS=1500`
  - `DISPLAY_FALLBACK_MIN_HOLD_MS=10000`
- Existing WebRTC tracks are rebuilt by the frontend when the display source changes.

### Main stream pressure reduction

- Main display stream can use lower subprocess output settings than the analysis stream:
  - `MAIN_CAPTURE_JPEG_QUALITY=55`
  - `MAIN_CAPTURE_PROCESS_OUTPUT_HEIGHT=720`
  - `MAIN_CAPTURE_PROCESS_WRITE_FPS=8`

### Observability

- `/status.main_stream` and `/status.analysis_stream` now expose:
  - `last_restart_at`
  - `last_restart_reason`
- `/status` exposes:
  - `display_source_current`
  - `display_fallback_active`
- Frontend debug counters include:
  - `webrtcReconnects`
  - `wsReconnects`
  - `displayFallbackSwitches`

## Verification

Static checks:

```text
python -m compileall app
conda run -n torchgpu python -c "from app.main import app; print('app import ok')"
node --check frontend_demo/app.js
node --check frontend_demo/overlay.js
```

60-second smoke test:

```text
main max frame_age_ms: 141
analysis max frame_age_ms: 110
main restart delta: 0
analysis restart delta: 0
tracking_worker_fps avg/min: 10.75 / 10.71
result_publish_fps avg/min: 9.22 / 9.19
detection_worker_fps avg: 4.28
pipeline errors: 0
GPU util: 14%
GPU memory: 1459 MB
```

10-minute runtime sample:

```text
sample_count: 600
status_failures: 0
main max frame_age_ms: 375
analysis max frame_age_ms: 156
main frame_age > 3000ms: 0
analysis frame_age > 3000ms: 0
main restart delta: 0
analysis restart delta: 0
fallback samples: 0
tracking_worker_fps avg/min: 10.79 / 10.71
result_publish_fps avg/min: 9.25 / 9.19
detection_worker_fps avg: 4.32
pipeline errors: 0
temporal errors: 0
GPU util avg/max: 15.41% / 20%
GPU memory max: 1465 MB
WebRTC clients max: 1
WebSocket clients max: 1
```

Raw log:

```text
logs/runtime_debug/phase5_16_p0_hardening_10min.json
```

Fault injection:

- Manually killed the `main_stream` capture subprocess.
- Backend restarted the subprocess and exposed `last_restart_reason=capture_process_exit`.
- Stream recovered quickly, so fallback did not need to activate during that injection.

## Current Boundary

- This phase improves recovery and visibility; it does not prove final 10-minute human-motion stability yet.
- If main stream stalls long enough to exceed the fallback threshold, new WebRTC offers will use `analysis_stream`.
- Existing WebRTC sessions are rebuilt by the frontend after display source changes.

## Next Test

Run real-person motion for at least 10 minutes and record:

- main/analysis restart delta
- WebRTC reconnect count
- WebSocket reconnect count
- display fallback switch count
- max frame age
- tracking/result publish FPS
- pose skipped due to busy
- CPU/GPU/memory
