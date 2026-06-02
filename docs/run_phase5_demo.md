# Run Phase 5 Demo

## Recommended Competition/Test Configuration

Phase 5 now recommends dual stream mode:

```text
main_stream (/tcp/av0_0)     -> WebRTC high-quality display
analysis_stream (/tcp/av0_1) -> AI analysis
```

Do not send the main stream to AI. The main stream is for display only.

Current RTSP baseline is fixed to port `10554`. Do not auto-fallback to
`554`, auto-try `8554`, mix multiple RTSP ports, or use `192.168.8.246`
as the current acceptance baseline unless explicitly instructed.

Standard dual-stream URL format:

```text
main:     rtsp://admin:***@<ip>:10554/tcp/av0_0
analysis: rtsp://admin:***@<ip>:10554/tcp/av0_1
```

Verified current baseline:

```text
main:     rtsp://admin:***@192.168.8.254:10554/tcp/av0_0
analysis: rtsp://admin:***@192.168.8.254:10554/tcp/av0_1
```

Recommended environment:

```text
ENABLE_DUAL_STREAM=true
MAIN_STREAM_URL=rtsp://admin:你的密码@192.168.8.254:10554/tcp/av0_0
ANALYSIS_STREAM_URL=rtsp://admin:你的密码@192.168.8.254:10554/tcp/av0_1
MAIN_CAPTURE_BACKEND=subprocess_opencv
ANALYSIS_CAPTURE_BACKEND=subprocess_opencv

CAPTURE_BACKEND=subprocess_opencv
CAPTURE_PROCESS_FRAME_TIMEOUT_MS=2000
CAPTURE_PROCESS_RESTART_MS=500
CAPTURE_JPEG_QUALITY=60
CAPTURE_PROCESS_OUTPUT_HEIGHT=720
CAPTURE_PROCESS_WRITE_FPS=10

ENABLE_TRACKING=true
ENABLE_IDENTITY_BINDING=true
IDENTITY_BINDING_ASYNC=true
ENABLE_POSE=true
ENABLE_BEHAVIOR=true
ENABLE_TEMPORAL=true
```

Replace `你的密码` with the camera plaintext password before testing. Do not commit real passwords.

## One-command Startup

From `D:\vision_service`:

```powershell
conda run -n torchgpu python scripts\start_phase5_test.py
```

The script starts:

```text
Identity Service -> http://127.0.0.1:8100
Vision Service   -> http://127.0.0.1:8000
Demo page        -> http://127.0.0.1:8000/demo?v=phase5-dual
```

Stop both services with `Ctrl+C` in the same terminal.

## Manual Startup

Identity service:

```powershell
cd D:\vision_service\identity_service
conda activate identity310
python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Vision service:

```powershell
cd D:\vision_service
conda activate torchgpu

$env:ENABLE_DUAL_STREAM="true"
$env:MAIN_STREAM_URL="rtsp://admin:你的密码@192.168.8.254:10554/tcp/av0_0"
$env:ANALYSIS_STREAM_URL="rtsp://admin:你的密码@192.168.8.254:10554/tcp/av0_1"
$env:DEFAULT_RTSP_URL="rtsp://admin:你的密码@192.168.8.254:10554/tcp/av0_1"
$env:CAPTURE_BACKEND="subprocess_opencv"
$env:MAIN_CAPTURE_BACKEND="subprocess_opencv"
$env:ANALYSIS_CAPTURE_BACKEND="subprocess_opencv"
$env:CAPTURE_PROCESS_FRAME_TIMEOUT_MS="2000"
$env:CAPTURE_PROCESS_RESTART_MS="500"
$env:CAPTURE_JPEG_QUALITY="60"
$env:CAPTURE_PROCESS_OUTPUT_HEIGHT="720"
$env:CAPTURE_PROCESS_WRITE_FPS="10"

$env:ENABLE_TRACKING="true"
$env:ENABLE_IDENTITY_BINDING="true"
$env:IDENTITY_BINDING_ASYNC="true"
$env:IDENTITY_SERVICE_URL="http://127.0.0.1:8100"
$env:ENABLE_POSE="true"
$env:POSE_PROVIDER="yolo"
$env:ENABLE_BEHAVIOR="true"
$env:ENABLE_TEMPORAL="true"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/demo?v=phase5-dual
```

## Expected Status

`/status` should show:

```text
display_source=main
analysis_source=analysis
main_stream.frame_width=1280
main_stream.frame_height=720
analysis_stream.frame_width=640
analysis_stream.frame_height=360
pipeline.tracking_worker_fps≈10
pipeline.result_publish_fps≈9
```

## Current Boundaries

- Fallback is not enabled yet. If the main stream fails, fallback to analysis display is a later phase.
- Overlay uses coordinate mapping from analysis to display frames.
- Fast movement can show slight overlay lag because main and analysis streams are not frame-synchronized.
- If the camera main/sub stream field of view changes, simple scaling may not be enough.
