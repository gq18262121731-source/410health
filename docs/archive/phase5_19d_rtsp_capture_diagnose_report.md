# Phase 5.19D RTSP Capture Diagnose Report

This phase diagnoses RTSP capture stability before pose activation. It does not modify pose models, fall logic, Temporal, WebRTC architecture, or alerting.

## Summary

- Camera connected ratio: `0.0`
- Camera capture_fps avg: `0.0`
- Camera frame_age max ms: `None`
- Analysis frame_age max ms: `None`
- Detection worker FPS avg: `0.0`
- Tracking worker FPS avg: `10.735`
- Publish FPS avg: `0.0`
- Detection objects max: `0.0`
- Tracking objects max: `0.0`
- Target objects max: `0.0`
- Pose attempts last: `0`
- Pose success last: `0`
- Pose skip reasons last: `{'no_tracking': 299}`
- Pose target source last: `none`

## Capture Errors

- Capture process errors seen: `['capture_process_open_failed url=rtsp://admin:***@192.168.8.250:10554/tcp/av0_1 elapsed_ms=50343.0', 'capture_process_open_start url=rtsp://admin:***@192.168.8.250:10554/tcp/av0_1 output_height=720 write_fps=10.0 buffersize=1']`
- Camera errors seen: `['capture process stream closed']`

## Artifact

- `D:\vision_service\logs\runtime_debug\phase5_19d_rtsp_capture_diagnose.json`
