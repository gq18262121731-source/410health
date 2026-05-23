# Identity Service

Standalone identity enrollment and matching service.

It does not connect to RTSP, YOLO, WebRTC, or the main Vision Service runtime. It only handles:

- face enrollment
- embedding extraction
- local identity storage
- face matching

## Run

```powershell
cd D:\vision_service\identity_service
conda activate identity310
pip install -r requirements.txt
pip install -r requirements-identity.txt
uvicorn app.main:app --host 127.0.0.1 --port 8100
```

If InsightFace fails to load, the service still starts and `/healthz` reports `recognizer_loaded=false`.

## Endpoints

- `GET /healthz`
- `POST /identity/enroll`
- `POST /identity/match`
- `GET /identity/list`
- `DELETE /identity/{person_id}`

## Enroll

```powershell
curl.exe -X POST "http://127.0.0.1:8100/identity/enroll" `
  -F "person_id=elder_001" `
  -F "person_name=张奶奶" `
  -F "replace_existing=true" `
  -F "files=@D:\faces\elder_001_1.jpg" `
  -F "files=@D:\faces\elder_001_2.jpg"
```

## Match

```powershell
curl.exe -X POST "http://127.0.0.1:8100/identity/match" `
  -F "threshold=0.45" `
  -F "file=@D:\faces\candidate.jpg"
```

## Storage

```text
data/identities/
  elder_001/
    profile.json
    embeddings.npy
    faces/
      001.jpg
      002.jpg
```

Embeddings are saved as float32 and L2 normalized.

## Safety

- Do not log image bytes, base64, or raw embeddings.
- InsightFace failure only affects identity APIs.
- The main Vision Service is not modified by this service.
