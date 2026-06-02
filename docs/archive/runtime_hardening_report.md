# Phase 5.20 Runtime Hardening Review

Generated at: 2026-05-25

## Scope

Phase 5.20 reviewed the Phase 5.17-5.19 runtime hardening stack:

- Phase 5.17 Observability Foundation
- Phase 5.18 Worker Watchdog
- Phase 5.19 Replay Regression

This phase did not change models, Temporal, FallStateMachine, alert POST, snapshots, GRU/LSTM, or fall thresholds.

## Validation Summary

| Area | Result |
| --- | --- |
| `service_state` aggregation | PASS |
| `diagnostics` flags | PASS |
| Watchdog healthy-worker behavior | PASS |
| Watchdog targeted restart behavior | PASS |
| Watchdog degraded/suppressed behavior | PASS |
| Replay regression gate | PASS |
| Compile/import | PASS |

Artifacts:

- `logs/runtime_debug/phase5_20_runtime_hardening_validation.json`
- `logs/regression/regression_report.json`
- `logs/regression/regression_report.md`

## Commands Run

```powershell
python -m compileall app scripts\replay_regression.py
conda run -n torchgpu python -c "from app.main import app; from app.services.watchdog_service import WatchdogService; import scripts.replay_regression as rr; print('phase520 import ok')"
conda run -n torchgpu python scripts\replay_regression.py --frame-stride 10 --max-frames 120
```

The synthetic status/watchdog validation was run with a temporary script that directly exercised the current `StatusService` and `WatchdogService` logic without requiring a live camera.

## Service State And Diagnostics

| Scenario | Expected State | Actual State | Key Diagnostic | Result |
| --- | --- | --- | --- | --- |
| Normal streams and workers | `normal` | `normal` | all false | PASS |
| Both streams connecting/disconnected | `camera_lost` | `camera_lost` | `camera_lost=true` | PASS |
| Main stream frame age > 3000ms | `capture_stale` | `capture_stale` | `capture_stale=true` | PASS |
| Main stream state is `stale` | `capture_stale` | `capture_stale` | `capture_stale=true` | PASS |
| Detection latency > 1000ms | `inference_slow` | `inference_slow` | `inference_slow=true` | PASS |
| Detection worker FPS < 1 | `inference_slow` | `inference_slow` | `inference_slow=true` | PASS |
| Result publish FPS < 6 | `publisher_slow` | `publisher_slow` | `publisher_slow=true` | PASS |
| Pose skipped due to busy >= 50 | `degraded` | `degraded` | `pose_degraded=true` | PASS |
| Pose circuit breaker open | `degraded` | `degraded` | `pose_degraded=true` | PASS |
| No WebRTC and no WebSocket clients | `frontend_disconnected` | `frontend_disconnected` | `frontend_disconnected=true` | PASS |
| Watchdog degraded override | `degraded` | `degraded` | watchdog degraded | PASS |

Finding: `frontend_disconnected` is currently treated as a service state when both `webrtc_clients=0` and `ws_clients=0`. This is accurate for demo/runtime supervision, but it should be interpreted as "no active frontend clients", not as a backend failure.

## Watchdog Behavior

| Scenario | Expected Behavior | Actual Behavior | Result |
| --- | --- | --- | --- |
| Healthy workers | No restart | No capture/detection restart; watchdog remains `normal` | PASS |
| Capture stale | Restart only capture worker | Capture restart count increments; detection untouched | PASS |
| Detection heartbeat timeout | Restart only detection worker | Detection restart count increments; capture untouched | PASS |
| Worker cannot stop safely | Enter degraded/suppressed instead of duplicating worker | `watchdog_state=degraded`, `watchdog_suppressed=true` | PASS |
| Restart storm exceeds max count | Suppress repeated restarts | `suppressed_workers` includes `camera_01:detection` | PASS |

Notes:

- Watchdog does not falsely restart healthy workers in the synthetic healthy case.
- Watchdog restarts only the affected worker in targeted failure cases.
- If a Python worker cannot stop cleanly, watchdog refuses to start a duplicate worker and marks degraded. This is the intended safety boundary.
- Restart storm suppression works through `WATCHDOG_MAX_RESTART_COUNT` and `WATCHDOG_RESTART_WINDOW_MS`.

## Replay Regression Gate

Replay command:

```powershell
conda run -n torchgpu python scripts\replay_regression.py --frame-stride 10 --max-frames 120
```

Result:

```json
{"case_count": 3, "failed": []}
```

| Case | Label | Pass | Max State | Max Prob | Confirmed | Processed Frames | Detect FPS | Pose FPS | Avg Latency |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| `standing_fixture` | normal | PASS | `normal` | 0.05 | false | 8 | 12.77 | 34.22 | 136.75ms |
| `hard_negative_bus_person` | hard_negative | PASS | `normal` | 0.05 | false | 12 | 63.44 | 64.07 | 32.25ms |
| `ur_fall_01` | fall | PASS | `falling` | 0.67 | false | 12 | 87.78 | 97.93 | 22.51ms |

Replay regression is suitable as a fixed gate for future worker/rule/model/config changes. The current fixture set is intentionally minimal, so it should be expanded before treating it as a full accuracy gate.

## Gate Recommendation

Use this as the minimum pre-merge/runtime gate after future changes:

```powershell
python -m compileall app scripts\replay_regression.py
conda run -n torchgpu python -c "from app.main import app; from app.services.watchdog_service import WatchdogService; import scripts.replay_regression as rr; print('import ok')"
conda run -n torchgpu python scripts\replay_regression.py --frame-stride 10 --max-frames 120
```

For changes touching runtime stability, also rerun the synthetic status/watchdog validation represented by:

```text
logs/runtime_debug/phase5_20_runtime_hardening_validation.json
```

## Conclusion

Phase 5.20 passes.

The system can now:

- expose which layer is unhealthy through `/status.service_state` and `/status.diagnostics`
- show per-worker health through `/status.workers`
- recover individual stale workers through watchdog
- avoid restart storms through degraded/suppressed state
- run fixed-video replay regression without a live camera

No runtime hardening code changes were required in this phase.
