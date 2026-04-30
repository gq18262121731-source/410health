from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import get_settings
from backend.dependencies import get_camera_frame_hub
from backend.dependencies import get_camera_audio_hub
from backend.dependencies import get_camera_talk_service
from backend.dependencies import get_camera_web_talk_service
from backend.services.camera_service import CameraService


router = APIRouter(prefix="/camera", tags=["camera"])


class CameraPtzRequest(BaseModel):
    direction: str
    mode: str = "pulse"


@router.get("/status")
async def camera_status() -> dict[str, object]:
    status = CameraService(get_settings()).check_status()
    return {
        "configured": status.configured,
        "online": status.online,
        "ip": status.ip,
        "port": status.port,
        "path": status.path,
        "checked_at": status.checked_at.isoformat(),
        "latency_ms": status.latency_ms,
        "error": status.error,
    }


@router.get("/stream-status")
async def camera_stream_status() -> dict[str, object]:
    return get_camera_frame_hub().status()


@router.get("/audio/status")
async def camera_audio_status() -> dict[str, object]:
    status = await asyncio.to_thread(CameraService(get_settings()).check_audio_status)
    return {
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


@router.get("/audio/stream-status")
async def camera_audio_stream_status() -> dict[str, object]:
    return get_camera_audio_hub().status()


@router.get("/talk/status")
async def camera_talk_status() -> dict[str, object]:
    return {
        "local_activex": get_camera_talk_service().status(),
        "web_microphone": get_camera_web_talk_service().status(),
    }


@router.post("/talk/start")
async def camera_talk_start() -> dict[str, object]:
    try:
        return await asyncio.to_thread(get_camera_talk_service().start)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/talk/stop")
async def camera_talk_stop() -> dict[str, object]:
    return await asyncio.to_thread(get_camera_talk_service().stop)


@router.get("/talk/web/status")
async def camera_web_talk_status() -> dict[str, object]:
    return get_camera_web_talk_service().status()


@router.post("/talk/web/stop")
async def camera_web_talk_stop() -> dict[str, object]:
    return await asyncio.to_thread(get_camera_web_talk_service().stop)


@router.get("/snapshot")
async def camera_snapshot() -> Response:
    try:
        image_bytes, headers = CameraService(get_settings()).capture_jpeg()
    except RuntimeError as exc:
        code = str(exc)
        status_code = 503
        if code == "CAMERA_NOT_CONFIGURED":
            status_code = 400
        raise HTTPException(status_code=status_code, detail=code) from exc

    return Response(content=image_bytes, media_type="image/jpeg", headers=headers)


@router.get("/stream.mjpg")
async def camera_stream() -> StreamingResponse:
    try:
        frames = CameraService(get_settings()).mjpeg_frames()
    except RuntimeError as exc:
        code = str(exc)
        status_code = 503
        if code == "CAMERA_NOT_CONFIGURED":
            status_code = 400
        raise HTTPException(status_code=status_code, detail=code) from exc

    return StreamingResponse(
        frames,
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.post("/ptz")
async def camera_ptz(payload: CameraPtzRequest) -> dict[str, object]:
    try:
        return await asyncio.to_thread(CameraService(get_settings()).ptz_move, payload.direction, payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        code = str(exc)
        status_code = 503
        if code == "CAMERA_NOT_CONFIGURED":
            status_code = 400
        raise HTTPException(status_code=status_code, detail=code) from exc
