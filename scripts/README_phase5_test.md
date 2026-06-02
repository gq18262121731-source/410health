# Phase 5 Test Launcher

Use this helper for live browser testing. It starts the standalone
`identity_service` and the main `vision_service` in separate conda environments.

```powershell
cd D:\vision_service
conda run -n torchgpu python scripts\start_phase5_test.py
```

The script starts:

- Identity Service: `http://127.0.0.1:8100`
- Vision Service: `http://127.0.0.1:8000`
- Demo page: `http://127.0.0.1:8000/demo?v=phase53`

The current RTSP baseline uses fixed port `10554`; do not auto-fallback to
`554`, auto-try `8554`, mix multiple RTSP ports, or use `192.168.8.246`
as the current acceptance baseline unless explicitly instructed.

The demo RTSP field is prefilled with this editable analysis-stream template:

```text
rtsp://admin:YOUR_PASSWORD@192.168.8.254:10554/tcp/av0_1
```

Standard dual-stream format:

```text
main:     rtsp://admin:YOUR_PASSWORD@192.168.8.254:10554/tcp/av0_0
analysis: rtsp://admin:YOUR_PASSWORD@192.168.8.254:10554/tcp/av0_1
```

In the actual page, replace the password placeholder with the camera password
before clicking `Start`. Do not include real passwords in screenshots.

Press `Ctrl+C` in the launcher window to stop both services.
