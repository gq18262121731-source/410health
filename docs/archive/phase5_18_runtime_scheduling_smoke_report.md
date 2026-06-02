# Phase 5.18 Runtime Scheduling Report

This phase tunes runtime scheduling only. It does not change YOLO model weights, Temporal, alert behavior, WebRTC architecture, or cloud deployment strategy.

## Matrix

| Scenario | Detection Interval | YOLO ImgSz | Detect FPS Avg | Tracking FPS Avg | Publish FPS Avg | Pose FPS Avg | Pose Skipped Busy | Main >3000ms | Analysis >3000ms | GPU Avg | GPU Max | Pipeline Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_baseline | 200 | 640 | 0.0 | 10.697 | 0.0 | 0.0 | 0 | 0 | 0 | 7.667 | 10.0 | 0 |
| B_balanced | 125 | 512 | 0.0 | 10.713 | 0.0 | 0.0 | 0 | 0 | 0 | 7.667 | 10.0 | 0 |
| C_fast | 100 | 416 | 0.0 | 10.698 | 0.0 | 0.0 | 0 | 0 | 0 | 7.833 | 9.0 | 0 |
| D_aggressive | 67 | 416 | 0.0 | 10.712 | 0.0 | 0.0 | 0 | 0 | 0 | 7.0 | 8.0 | 0 |

## Recommendation

- Recommended scenario: `A_baseline`
- Recommended config: `{'DETECTION_INTERVAL_MS': 200, 'YOLO_IMGSZ': 640, 'YOLO_DEVICE': 'cuda:0', 'POSE_FPS': 1, 'POSE_WORKER_FPS': 1, 'YOLO_POSE_IMGSZ': 320, 'YOLO_POSE_DEVICE': 'cuda:0'}`

## Why Not Cloud

- The local 4060 Ti already has large inference headroom.
- The current bottleneck is runtime scheduling, not raw compute shortage.
- Cloud would add RTSP transport, network latency, and deployment complexity without fixing the actual limiter.

## Why Not TensorRT Yet

- Offline detect-only and detect+pose throughput are already far above live runtime throughput.
- The live bottleneck is cadence and inference lock contention.
- TensorRT would add environment complexity before the real bottleneck is addressed.

## Target-only Pose Next Step

- If the recommended scenario still leaves pose too low or skipped-too-busy too high, target-only pose is the next runtime optimization to pursue.

## Artifacts

- `D:\vision_service\logs\runtime_debug\phase5_18_runtime_scheduling.json`
- `D:\vision_service\docs\phase5_18_runtime_scheduling_report.md`
