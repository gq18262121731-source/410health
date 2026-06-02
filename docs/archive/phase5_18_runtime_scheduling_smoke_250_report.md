# Phase 5.18 Runtime Scheduling Report

This phase tunes runtime scheduling only. It does not change YOLO model weights, Temporal, alert behavior, WebRTC architecture, or cloud deployment strategy.

## Matrix

| Scenario | Detection Interval | YOLO ImgSz | Detect FPS Avg | Tracking FPS Avg | Publish FPS Avg | Pose FPS Avg | Pose Skipped Busy | Main >3000ms | Analysis >3000ms | GPU Avg | GPU Max | Pipeline Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_baseline | 200 | 640 | 5.605 | 10.637 | 9.172 | 0.0 | 0 | 0 | 0 | 7.333 | 9.0 | 0 |
| B_balanced | 125 | 512 | 8.523 | 10.724 | 9.281 | 0.135 | 1 | 0 | 0 | 7.5 | 10.0 | 0 |
| C_fast | 100 | 416 | 8.859 | 10.742 | 8.959 | 0.017 | 0 | 0 | 0 | 10.5 | 12.0 | 0 |
| D_aggressive | 67 | 416 | 9.348 | 10.724 | 9.275 | 0.0 | 0 | 0 | 0 | 10.333 | 13.0 | 0 |

## Recommendation

- Recommended scenario: `B_balanced`
- Recommended config: `{'DEFAULT_RTSP_URL': 'rtsp://admin:410410410@192.168.8.250:10554/tcp/av0_1', 'MAIN_STREAM_URL': 'rtsp://admin:410410410@192.168.8.250:10554/tcp/av0_0', 'ANALYSIS_STREAM_URL': 'rtsp://admin:410410410@192.168.8.250:10554/tcp/av0_1', 'DETECTION_INTERVAL_MS': 125, 'YOLO_IMGSZ': 512, 'YOLO_DEVICE': 'cuda:0', 'POSE_FPS': 1, 'POSE_WORKER_FPS': 1, 'YOLO_POSE_IMGSZ': 320, 'YOLO_POSE_DEVICE': 'cuda:0'}`

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
