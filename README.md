# Vision Service

Standalone realtime vision service for the elderly-care project.

Current baseline:

- Phase 1: RTSP capture, latest-frame buffer, WebRTC video, WebSocket results, health status, Ultralytics YOLO person detect.
- Phase 2.1: ByteTrack-based tracking over existing YOLO detections.
- Phase 2.2: Identity enrollment API and local identity profile storage.

The service must not duplicate RTSP pulls. Realtime processing follows:

```text
RTSP
-> CaptureWorker
-> FrameBuffer
-> YOLO person detect
-> ByteTrack tracking
-> WebRTC video + WebSocket results
```

Identity enrollment is a sidecar management capability. It does not participate in realtime tracking until a later phase.

## Run

Recommended local GPU environment:

```powershell
cd D:\vision_service
conda activate torchgpu
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/demo
```

The service starts a mock camera by default when `DEFAULT_RTSP_URL` is empty. To use a real source, call:

```powershell
$body = @{
  camera_id = "camera_01"
  rtsp_url = "rtsp://user:password@host/stream"
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:8000/stream/start `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

## Key Endpoints

- `GET /healthz`
- `GET /status`
- `POST /stream/start`
- `POST /stream/stop`
- `GET /integration/results/latest`
- `GET /integration/results/{camera_id}/latest`
- `POST /webrtc/offer`
- `WS /ws/results?camera_id=camera_01`
- `POST /identity/enroll`
- `GET /identity/list`
- `DELETE /identity/{person_id}`

## LAN Integration

If another server on the same LAN only needs AI results and does not need to render video,
use the polling-friendly integration endpoints instead of WebRTC/WebSocket.

Run the service on a LAN-accessible host and bind to all interfaces:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then the other server can call:

- `GET http://<vision-host>:8000/integration/results/latest`
- `GET http://<vision-host>:8000/integration/results/camera_01/latest`

Single-camera response example:

```json
{
  "ok": true,
  "camera_id": "camera_01",
  "has_result": true,
  "result": {
    "type": "vision_result",
    "camera_id": "camera_01",
    "timestamp": "2026-05-27T06:25:31.123+00:00",
    "frame_seq": 128,
    "frame_width": 1280,
    "frame_height": 720,
    "objects": [
      {
        "label": "person",
        "confidence": 0.94,
        "bbox": [120, 80, 420, 680],
        "track_id": 3,
        "is_target": true,
        "person_id": null,
        "person_name": null,
        "identity_state": "target_locked"
      }
    ],
    "detector": {
      "latency_ms": 42.7
    }
  },
  "message": "ok"
}
```

If the camera exists but no result has been published yet, `has_result` returns `false`.
If the camera ID does not exist, the service returns `404`.

## Config

Important phase flags:

```text
ENABLE_TRACKING=true
ENABLE_IDENTITY=false
ENABLE_TARGET_BINDING=false
```

Identity enrollment config:

```text
IDENTITY_STORE_DIR=data/identities
IDENTITY_MAX_IMAGES=5
INSIGHTFACE_MODEL_NAME=buffalo_l
INSIGHTFACE_CTX_ID=0
INSIGHTFACE_DET_SIZE=640
INSIGHTFACE_PROVIDERS=
```

Set `ENABLE_IDENTITY=true` before using `/identity/enroll`. If InsightFace fails to load, the service still starts. Only the identity API returns a clear error.

Install optional identity dependencies separately:

```powershell
pip install -r requirements-identity.txt
```

On Windows, `insightface` may try to build native extensions if a wheel is not available. If that happens, install Microsoft C++ Build Tools or use a Conda/package source that provides a compatible prebuilt package.

## RTSP Health

`connected=true` only means the capture backend believes the source is open. It does not guarantee that fresh frames are still arriving.

Use these fields together:

- `stream_state`: `disconnected`, `connecting`, `connected`, `stale`, or `reconnecting`.
- `frame_age_ms`: age of the latest frame in the shared `FrameBuffer`.
- `capture_fps`: recent capture FPS.
- `reconnect_count`: number of reconnect attempts.
- `last_frame_at`: UTC timestamp of the latest captured frame.

Default stale thresholds:

```text
STREAM_STALE_THRESHOLD_MS=3000
STREAM_STALE_RECONNECT_AFTER_MS=6000
```

If `stream_state=stale`, the RTSP TCP connection may still be alive, but the image is no longer updating. The frontend should show this as "画面停滞/正在恢复", not as a normal connection.

The current implementation uses OpenCV timeout properties plus a lightweight watchdog. If `cv2.VideoCapture.read()` blocks inside the native backend longer than expected, watchdog execution can be delayed. If this becomes frequent in deployment, the next engineering step is a subprocess or FFmpeg-based capture worker, not adding model logic.

## Tracking

Tracking consumes existing YOLO detections:

```text
FrameBuffer -> YOLO detections -> ByteTrack.update()
```

It does not call `model.track(rtsp_url)` and does not open RTSP.

WebSocket object example:

```json
{
  "track_id": 3,
  "label": "person",
  "bbox": [10, 20, 100, 220],
  "confidence": 0.92,
  "is_target": true,
  "person_id": null,
  "person_name": null,
  "identity_state": "target_locked"
}
```

Phase 2.1 target selection is temporary and tracking-only. It is not a real elderly identity binding.

## Identity Enrollment

Phase 2.2 supports local identity registration only. It does not bind identities to realtime tracks yet.

Enable identity:

```powershell
$env:ENABLE_IDENTITY="true"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Enroll with multipart files:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/identity/enroll" `
  -F "person_id=elder_001" `
  -F "person_name=张奶奶" `
  -F "replace_existing=true" `
  -F "files=@D:\faces\elder_001_1.jpg" `
  -F "files=@D:\faces\elder_001_2.jpg"
```

Response:

```json
{
  "person_id": "elder_001",
  "person_name": "张奶奶",
  "faces_registered": 2,
  "status": "success"
}
```

List identities:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/identity/list |
  ConvertTo-Json -Depth 10
```

Delete identity:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/identity/elder_001 -Method DELETE
```

Storage layout:

```text
data/identities/
  elder_001/
    profile.json
    embeddings.npy
    faces/
      001.jpg
      002.jpg
```

`embeddings.npy` stores L2-normalized embeddings. `profile.json` records:

```json
{
  "person_id": "elder_001",
  "person_name": "张奶奶",
  "embedding_count": 2,
  "model_name": "buffalo_l",
  "created_at": "...",
  "updated_at": "..."
}
```

Safety boundaries:

- Do not log uploaded image bytes or base64.
- If no face is detected, `/identity/enroll` returns a clear `400` error.
- If InsightFace cannot load, `/identity/enroll` returns a clear `503` error.
- Identity failures do not affect RTSP, WebRTC, YOLO, or tracking.
