from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.config import get_settings
from backend.dependencies import (
    enrich_alarm_context,
    get_alarm_service,
    get_camera_audio_hub,
    get_camera_detection_frame_hub,
    get_camera_frame_hub,
    get_fall_detection_service,
    get_fall_multimodal_review_status,
    get_health_data_repository,
    get_websocket_manager,
    ingest_fall_detection_event,
)
from backend.models.alarm_model import AlarmLayer, AlarmPriority, AlarmRecord, AlarmType
from backend.services.camera_service import CameraService


router = APIRouter(prefix="/camera", tags=["camera"])


class CameraPtzRequest(BaseModel):
    direction: str
    mode: str = "pulse"


@router.get("/status")
async def camera_status() -> dict[str, object]:
    status = await asyncio.to_thread(CameraService(get_settings()).check_status)
    return {
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


@router.get("/fall-detection/status")
async def camera_fall_detection_status() -> dict[str, object]:
    payload = get_fall_detection_service().status()
    payload["multimodal_review"] = get_fall_multimodal_review_status()
    return payload


@router.get("/fall-detection/snapshot")
async def camera_fall_detection_snapshot(path: str) -> FileResponse:
    settings = get_settings()
    snapshot_dir = Path(settings.fall_detection_snapshot_dir).resolve()
    requested = Path(path)
    target = requested.resolve() if requested.is_absolute() else (snapshot_dir / requested).resolve()

    try:
        target.relative_to(snapshot_dir)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="SNAPSHOT_PATH_NOT_ALLOWED") from exc

    if not target.is_file():
        raise HTTPException(status_code=404, detail="SNAPSHOT_NOT_FOUND")

    return FileResponse(
        target,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.post("/fall-detection/simulate")
async def camera_fall_detection_simulate() -> AlarmRecord:
    settings = get_settings()
    if not settings.debug and settings.environment != "development":
        raise HTTPException(status_code=404, detail="Not found")

    snapshot_path: str | None = None
    snapshot_dir = Path(settings.fall_detection_snapshot_dir).resolve()
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    image_bytes = get_camera_frame_hub().latest_frame()
    try:
        if image_bytes is None:
            image_bytes, _headers = await asyncio.to_thread(CameraService(settings).capture_jpeg)
        snapshot_file = snapshot_dir / f"demo_fall_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jpg"
        snapshot_file.write_bytes(image_bytes)
        snapshot_path = str(snapshot_file)
    except RuntimeError:
        snapshot_path = None

    event = {
        "event_type": "fall_confirmed",
        "track_id": "demo-track-1",
        "incident_id": f"demo-track-1-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "state": "confirmed_fall",
        "severity": "L3",
        "fall_score": 0.87,
        "injury": {
            "level": "I3",
            "reason": "demo_confirmed_fall",
            "advice": "Please inspect the live view and contact on-site staff immediately.",
        },
        "snapshot_path": snapshot_path,
        "demo": True,
    }
    created = await ingest_fall_detection_event(event)
    if created is not None:
        return created

    fallback_alarm = AlarmRecord(
        device_mac=settings.fall_detection_target_device_mac,
        alarm_type=AlarmType.FALL_INJURY_RISK,
        alarm_level=AlarmPriority.CRITICAL,
        alarm_layer=AlarmLayer.REALTIME,
        message="Camera detected a fall event. Please inspect the live view immediately.",
        anomaly_probability=0.87,
        metadata={
            "source": "fall_detection_demo",
            "event": event,
            "severity": "L3",
            "injury_level": "I3",
            "track_id": "demo-track-1",
            "incident_id": event["incident_id"],
            "is_demo": True,
        },
    )
    return enrich_alarm_context(fallback_alarm)


@router.get("/snapshot")
async def camera_snapshot() -> Response:
    try:
        image_bytes, headers = await asyncio.to_thread(CameraService(get_settings()).capture_jpeg)
    except RuntimeError as exc:
        code = str(exc)
        status_code = 503
        if code == "CAMERA_NOT_CONFIGURED":
            status_code = 400
        raise HTTPException(status_code=status_code, detail=code) from exc

    return Response(content=image_bytes, media_type="image/jpeg", headers=headers)


@router.get("/stream.mjpg")
async def camera_stream() -> StreamingResponse:
    return StreamingResponse(
        get_camera_frame_hub().mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream.detect.mjpg")
async def camera_detection_stream() -> StreamingResponse:
    return StreamingResponse(
        get_camera_detection_frame_hub().mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
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
