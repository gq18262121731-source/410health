# Phase 5.19 Pose Smoothness / Quality Report

This phase compares pose cadence options and target-only pose behavior without changing fall logic, Temporal rules, or alerting.

## Matrix

| Scenario | Pose FPS Config | Target-only | Pose FPS Avg | Pose Latency Avg | Pose Latency P95 | Pose Latency Max | Pose Skipped Busy | Detect FPS Avg | Tracking FPS Avg | Publish FPS Avg | Main >3000ms | Analysis >3000ms | GPU Avg | CPU Avg |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_pose_1fps_baseline | 1 | false | 0.0 | None | None | None | 0 | 9.232 | 10.684 | 9.184 | 0 | 0 | 10.25 | 1.201 |
| B_pose_2fps | 2 | false | 0.0 | None | None | None | 0 | 9.079 | 10.685 | 9.043 | 0 | 0 | 9.75 | 1.262 |
| C_pose_5fps | 5 | false | 0.0 | None | None | None | 0 | 9.232 | 10.683 | 9.214 | 0 | 0 | 10.917 | 1.326 |
| D_target_only_pose_5fps | 5 | true | 0.0 | None | None | None | 0 | 9.238 | 10.679 | 9.198 | 0 | 0 | 9.5 | 1.014 |
| E_target_only_pose_10fps | 10 | true | 0.0 | None | None | None | 0 | 10.096 | 10.668 | 9.181 | 0 | 0 | 10.333 | 1.078 |

## Recommendation

- Recommended scenario: `A_pose_1fps_baseline`
- Recommended config: `{'DEFAULT_RTSP_URL': 'rtsp://admin:410410410@192.168.8.250:10554/tcp/av0_1', 'MAIN_STREAM_URL': 'rtsp://admin:410410410@192.168.8.250:10554/tcp/av0_0', 'ANALYSIS_STREAM_URL': 'rtsp://admin:410410410@192.168.8.250:10554/tcp/av0_1', 'DETECTION_INTERVAL_MS': 100, 'YOLO_IMGSZ': 416, 'YOLO_DEVICE': 'cuda:0', 'POSE_FPS': 1, 'POSE_WORKER_FPS': 1, 'YOLO_POSE_IMGSZ': 320, 'YOLO_POSE_DEVICE': 'cuda:0', 'POSE_TARGET_ONLY': 'false'}`

## Notes

- Current backend already uses target-preferred pose selection inside `PoseService`.
- Frontend smoothing/interpolation can make low backend pose FPS look less jerky without blocking detect.
- If pose >= 5 FPS is still not stable in full pipeline mode, target-only pose remains the next practical step.

## Artifacts

- `D:\vision_service\logs\runtime_debug\phase5_19_pose_quality.json`
- `D:\vision_service\docs\phase5_19_pose_quality_report.md`
