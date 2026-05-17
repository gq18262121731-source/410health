from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from backend.dependencies import (
    get_camera_source_audio_hub,
    get_camera_source_frame_hub,
    get_camera_source_registry,
    get_camera_source_settings,
)
from backend.services.camera_service import CameraService


router = APIRouter(prefix="/camera-sources", tags=["camera-sources"])
logger = logging.getLogger(__name__)


def _log_api_timing(name: str, started_at: float) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info("camera_source_api %s elapsed_ms=%.1f", name, elapsed_ms)


class CameraSourcePtzRequest(BaseModel):
    direction: str
    mode: str = "pulse"


class CameraSourceRegisterExternalRequest(BaseModel):
    device_id: str
    name: str = ""


class CameraSourceSelectRequest(BaseModel):
    camera_id: str


def _service_for(camera_id: str) -> CameraService:
    return CameraService(get_camera_source_settings(camera_id))


def _camera_not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc) or "CAMERA_SOURCE_NOT_FOUND")


@router.get("")
async def list_camera_sources() -> dict[str, object]:
    registry = get_camera_source_registry()
    return {
        "sources": [registry.public_source(source) for source in registry.list_sources()],
        "active_camera_id": registry.active_source().camera_id,
        "contract": "camera sources only extract video/audio/talk capabilities; UI and algorithms attach separately.",
    }


@router.get("/registration")
async def camera_source_registration_status() -> dict[str, object]:
    return get_camera_source_registry().registration_status()


@router.post("/registration/local/select")
async def camera_source_select_local() -> dict[str, object]:
    return get_camera_source_registry().select_local()


@router.post("/registration/external")
async def camera_source_register_external(payload: CameraSourceRegisterExternalRequest) -> dict[str, object]:
    try:
        return get_camera_source_registry().register_external(payload.device_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/registration/select")
async def camera_source_select(payload: CameraSourceSelectRequest) -> dict[str, object]:
    try:
        return get_camera_source_registry().select_source(payload.camera_id)
    except KeyError as exc:
        raise _camera_not_found(exc) from exc


@router.delete("/registration/external/{camera_id}")
async def camera_source_delete_external(camera_id: str) -> dict[str, object]:
    try:
        return get_camera_source_registry().delete_external(camera_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/active")
async def active_camera_source_detail() -> dict[str, object]:
    registry = get_camera_source_registry()
    return registry.public_source(registry.active_source())


@router.get("/active/status")
async def active_camera_source_status() -> dict[str, object]:
    started_at = time.perf_counter()
    active = get_camera_source_registry().active_source()
    payload = await camera_source_status(active.camera_id)
    _log_api_timing("camera-sources/active/status", started_at)
    return payload


@router.get("/active/snapshot")
async def active_camera_source_snapshot() -> Response:
    active = get_camera_source_registry().active_source()
    hub = get_camera_source_frame_hub(active.camera_id)
    await hub.start_keep_warm()
    frame = await hub.snapshot_frame(
        timeout_seconds=6.0,
        max_age_seconds=2.5,
    )
    if frame is not None:
        latest_frame_at = hub.latest_frame_at()
        age_ms = (
            int(max(0.0, (time.time() - latest_frame_at) * 1000))
            if latest_frame_at is not None
            else -1
        )
        return Response(
            content=frame,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Latest-Frame-At": "" if latest_frame_at is None else str(latest_frame_at),
                "X-Latest-Frame-Age-Ms": str(age_ms),
            },
        )
    if active.source_mode == "local":
        return await camera_source_snapshot(active.camera_id)
    return await camera_source_snapshot(active.camera_id)


@router.get("/active/stream-status")
async def active_camera_source_stream_status() -> dict[str, object]:
    started_at = time.perf_counter()
    active = get_camera_source_registry().active_source()
    hub = get_camera_source_frame_hub(active.camera_id)
    await hub.start_keep_warm()
    payload = await camera_source_stream_status(active.camera_id)
    payload["active_source_id"] = active.camera_id
    payload["requested_camera_id"] = "active"
    payload["hub_cache_key"] = active.camera_id.strip().lower()
    payload["hub_object_id"] = id(hub)
    _log_api_timing("camera-sources/active/stream-status", started_at)
    return payload


@router.get("/active/stream.mjpg")
async def active_camera_source_stream() -> StreamingResponse:
    active = get_camera_source_registry().active_source()
    if active.source_mode == "local":
        await get_camera_source_frame_hub(active.camera_id).start_keep_warm()
    return await camera_source_stream(active.camera_id)


@router.get("/active/video-preview", response_class=HTMLResponse)
async def active_camera_source_video_preview() -> HTMLResponse:
    html = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no"
    />
    <title>Camera Preview</title>
    <style>
      html, body {
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: #0f172a;
      }
      .stage {
        position: fixed;
        inset: 0;
        display: grid;
        place-items: center;
        background:
          radial-gradient(circle at 20% 20%, rgba(56, 189, 248, 0.12), transparent 32%),
          radial-gradient(circle at 80% 10%, rgba(14, 165, 233, 0.12), transparent 28%),
          #0f172a;
      }
      #video {
        width: 100%;
        height: 100%;
        object-fit: contain;
        display: block;
        background: #020617;
      }
      .badge {
        position: fixed;
        left: 12px;
        top: 12px;
        z-index: 5;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.76);
        color: #e2e8f0;
        font: 600 12px/1.2 sans-serif;
        border: 1px solid rgba(148, 163, 184, 0.28);
      }
    </style>
  </head>
  <body>
    <div class="stage">
      <div class="badge" id="stats">Latest Frame Preview</div>
      <img id="video" alt="camera preview" />
    </div>
    <script>
      const img = document.getElementById('video');
      const stats = document.getElementById('stats');
      let loading = false;
      let frames = 0;
      let lastStatsAt = performance.now();

      function updateStats() {
        const now = performance.now();
        const elapsed = (now - lastStatsAt) / 1000;
        if (elapsed < 1) return;
        const fps = frames / elapsed;
        stats.textContent = `Latest Frame ${fps.toFixed(1)} fps`;
        frames = 0;
        lastStatsAt = now;
      }

      function tick() {
        if (loading) {
          updateStats();
          return;
        }
        loading = true;
        const ts = Date.now();
        const next = new Image();
        next.onload = () => {
          img.src = next.src;
          frames += 1;
          loading = false;
          updateStats();
        };
        next.onerror = () => {
          loading = false;
          updateStats();
        };
        next.src = `/api/v1/camera-sources/active/snapshot?ts=${ts}`;
      }

      setInterval(tick, 200);
      tick();
    </script>
  </body>
</html>
"""
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/active/audio/status")
async def active_camera_source_audio_status() -> dict[str, object]:
    started_at = time.perf_counter()
    active = get_camera_source_registry().active_source()
    payload = await camera_source_audio_status(active.camera_id)
    _log_api_timing("camera-sources/active/audio/status", started_at)
    return payload


@router.get("/active/audio/stream-status")
async def active_camera_source_audio_stream_status() -> dict[str, object]:
    active = get_camera_source_registry().active_source()
    return await camera_source_audio_stream_status(active.camera_id)


@router.post("/active/ptz")
async def active_camera_source_ptz(payload: CameraSourcePtzRequest) -> dict[str, object]:
    active = get_camera_source_registry().active_source()
    return await camera_source_ptz(active.camera_id, payload)


@router.get("/{camera_id}")
async def camera_source_detail(camera_id: str) -> dict[str, object]:
    registry = get_camera_source_registry()
    try:
        return registry.public_source(registry.get_source(camera_id))
    except KeyError as exc:
        raise _camera_not_found(exc) from exc


@router.get("/{camera_id}/status")
async def camera_source_status(camera_id: str) -> dict[str, object]:
    try:
        status = await asyncio.to_thread(_service_for(camera_id).check_status)
    except KeyError as exc:
        raise _camera_not_found(exc) from exc
    return {
        "camera_id": camera_id,
        "configured": status.configured,
        "online": status.online,
        "ip": status.ip,
        "port": status.port,
        "path": status.path,
        "checked_at": status.checked_at.isoformat(),
        "latency_ms": status.latency_ms,
        "error": status.error,
        "source": status.source,
        "detail": status.detail,
    }


@router.get("/{camera_id}/snapshot")
async def camera_source_snapshot(camera_id: str) -> Response:
    try:
        image_bytes, headers = await asyncio.to_thread(_service_for(camera_id).capture_jpeg)
    except KeyError as exc:
        raise _camera_not_found(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=image_bytes, media_type="image/jpeg", headers=headers)


@router.get("/{camera_id}/stream-status")
async def camera_source_stream_status(camera_id: str) -> dict[str, object]:
    try:
        hub = get_camera_source_frame_hub(camera_id)
        status = hub.status()
    except KeyError as exc:
        raise _camera_not_found(exc) from exc
    return {
        "camera_id": camera_id,
        "requested_camera_id": camera_id,
        "hub_cache_key": camera_id.strip().lower(),
        "hub_object_id": id(hub),
        **status,
    }


@router.get("/{camera_id}/stream.mjpg")
async def camera_source_stream(camera_id: str) -> StreamingResponse:
    try:
        hub = get_camera_source_frame_hub(camera_id)
    except KeyError as exc:
        raise _camera_not_found(exc) from exc
    return StreamingResponse(
        hub.mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{camera_id}/audio/status")
async def camera_source_audio_status(camera_id: str) -> dict[str, object]:
    try:
        status = await asyncio.to_thread(_service_for(camera_id).check_audio_status)
    except KeyError as exc:
        raise _camera_not_found(exc) from exc
    return {
        "camera_id": camera_id,
        "configured": status.configured,
        "listen_supported": status.listen_supported,
        "talk_supported": status.talk_supported,
        "checked_url": status.checked_url,
        "audio_codec": status.audio_codec,
        "sample_rate": status.sample_rate,
        "channels": status.channels,
        "source": status.source,
        "sdk_available": status.sdk_available,
        "sdk_arch": status.sdk_arch,
        "sdk_loadable": status.sdk_loadable,
        "sdk_message": status.sdk_message,
        "gateway_configured": status.gateway_configured,
        "activex_available": status.activex_available,
        "activex_clsid": status.activex_clsid,
        "activex_inproc_path": status.activex_inproc_path,
        "activex_message": status.activex_message,
        "error": status.error,
    }


@router.get("/{camera_id}/audio/stream-status")
async def camera_source_audio_stream_status(camera_id: str) -> dict[str, object]:
    try:
        status = get_camera_source_audio_hub(camera_id).status()
    except KeyError as exc:
        raise _camera_not_found(exc) from exc
    return {"camera_id": camera_id, **status}


@router.get("/{camera_id}/talk/status")
async def camera_source_talk_status(camera_id: str) -> dict[str, object]:
    audio = await camera_source_audio_status(camera_id)
    return {
        "camera_id": camera_id,
        "talk_supported": bool(audio.get("talk_supported")),
        "strategy": "vendor-gateway-or-activex" if audio.get("talk_supported") else "not_available_yet",
        "gateway_configured": audio.get("gateway_configured"),
        "sdk_available": audio.get("sdk_available"),
        "sdk_arch": audio.get("sdk_arch"),
        "sdk_loadable": audio.get("sdk_loadable"),
        "activex_available": audio.get("activex_available"),
        "message": (
            "Talkback can be attempted through a configured vendor gateway or ActiveX bridge."
            if audio.get("talk_supported")
            else "No usable vendor talkback bridge is configured. RTSP/ONVIF listen does not by itself send microphone audio to the camera speaker."
        ),
    }


@router.post("/{camera_id}/ptz")
async def camera_source_ptz(camera_id: str, payload: CameraSourcePtzRequest) -> dict[str, object]:
    try:
        result = await asyncio.to_thread(_service_for(camera_id).ptz_move, payload.direction, payload.mode)
    except KeyError as exc:
        raise _camera_not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"camera_id": camera_id, **result}
