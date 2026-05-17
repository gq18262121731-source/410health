from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.config import get_settings
from backend.dependencies import (
    enrich_alarm_context,
    get_alarm_service,
    get_camera_detection_frame_hub,
    get_camera_pose_frame_hub,
    get_camera_setup_config_service,
    get_camera_source_audio_hub,
    get_camera_source_frame_hub,
    get_camera_source_registry,
    get_camera_source_settings,
    get_fall_detection_service,
    get_fall_frame_analysis_worker_service,
    get_fall_multimodal_review_status,
    get_frame_analysis_worker_service,
    get_health_data_repository,
    get_pose_detection_config_service,
    get_pose_detection_service,
    get_pose_frame_analysis_worker_service,
    get_websocket_manager,
    ingest_fall_detection_event,
    shutdown_camera_source_hubs,
)
from backend.models.alarm_model import AlarmLayer, AlarmPriority, AlarmRecord, AlarmType
from backend.services.camera_service import CameraService


router = APIRouter(prefix="/camera", tags=["camera"])
logger = logging.getLogger(__name__)


class CameraPtzRequest(BaseModel):
    direction: str
    mode: str = "pulse"


class CameraSetupConfigRequest(BaseModel):
    camera_source_mode: str | None = None
    camera_local_index: int | None = None
    camera_local_backend: str | None = None
    camera_ip: str | None = None
    camera_user: str | None = None
    camera_password: str | None = None
    camera_rtsp_port: int | None = None
    camera_rtsp_path: str | None = None
    camera_stream_rtsp_path: str | None = None
    camera_audio_rtsp_path: str | None = None
    camera_onvif_port: int | None = None


class PoseDetectionConfigRequest(BaseModel):
    pose_detection_enabled: bool | None = None
    pose_detection_profile: str | None = None
    pose_detection_process_every_override: int | None = None
    pose_detection_pose_conf_threshold: float | None = None
    pose_detection_analysis_width: int | None = None
    pose_detection_floor_roi_rect: str | None = None


class DetectionEnabledRequest(BaseModel):
    enabled: bool


class DetectionModelsEnabledRequest(BaseModel):
    fall_detection_enabled: bool | None = None
    pose_detection_enabled: bool | None = None


def _persist_env_value(key: str, value: str) -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    next_lines: list[str] = []
    applied = False
    for raw_line in lines:
        if "=" not in raw_line or raw_line.lstrip().startswith("#"):
            next_lines.append(raw_line)
            continue
        current_key, _sep, _current_value = raw_line.partition("=")
        if current_key.strip().upper() == key:
            next_lines.append(f"{key}={value}")
            applied = True
        else:
            next_lines.append(raw_line)
    if not applied:
        next_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def _camera_detection_models_status() -> dict[str, object]:
    fall_status = get_fall_detection_service().status()
    fall_status["multimodal_review"] = get_fall_multimodal_review_status()
    fall_status["resolved_target_device_mac"] = get_settings().resolved_fall_detection_target_device_mac
    return {
        "ok": True,
        "fall_detection": fall_status,
        "pose_detection": get_pose_detection_service().status(),
        "frame_analysis": get_frame_analysis_worker_service().status(),
    }


def _log_api_timing(name: str, started_at: float) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info("camera_api %s elapsed_ms=%.1f", name, elapsed_ms)


@router.get("/status")
async def camera_status() -> dict[str, object]:
    started_at = time.perf_counter()
    active = get_camera_source_registry().active_source()
    status = await asyncio.to_thread(CameraService(get_camera_source_settings("active")).check_status)
    payload = {
        "camera_id": active.camera_id,
        "camera_name": active.name,
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
    _log_api_timing("camera/status", started_at)
    return payload


@router.get("/stream-status")
async def camera_stream_status() -> dict[str, object]:
    started_at = time.perf_counter()
    active = get_camera_source_registry().active_source()
    payload = {"camera_id": active.camera_id, **get_camera_source_frame_hub("active").status()}
    _log_api_timing("camera/stream-status", started_at)
    return payload


@router.get("/setup/config")
async def camera_setup_config() -> dict[str, object]:
    return get_camera_setup_config_service().current()


@router.post("/setup/config")
async def camera_setup_config_update(payload: CameraSetupConfigRequest) -> dict[str, object]:
    config_service = get_camera_setup_config_service()
    current = config_service.update(payload.model_dump(exclude_none=True))
    await shutdown_camera_source_hubs()
    return {"ok": True, "config": current}


@router.post("/setup/test-snapshot")
async def camera_setup_test_snapshot(payload: CameraSetupConfigRequest) -> Response:
    config_service = get_camera_setup_config_service()
    settings = config_service.temporary_settings(payload.model_dump(exclude_none=True))
    if settings.camera_source_mode == "local":
        raise HTTPException(
            status_code=409,
            detail=(
                "LOCAL_BROWSER_CAMERA_ONLY: local camera preview is captured "
                "in the browser; backend OpenCV test snapshots are disabled"
            ),
        )
    try:
        image_bytes, headers = await asyncio.to_thread(CameraService(settings).capture_jpeg)
    except RuntimeError as exc:
        code = str(exc)
        status_code = 503
        if code == "CAMERA_NOT_CONFIGURED":
            status_code = 400
        raise HTTPException(status_code=status_code, detail=code) from exc
    return Response(content=image_bytes, media_type="image/jpeg", headers=headers)


@router.get("/audio/status")
async def camera_audio_status() -> dict[str, object]:
    started_at = time.perf_counter()
    active = get_camera_source_registry().active_source()
    status = await asyncio.to_thread(CameraService(get_camera_source_settings("active")).check_audio_status)
    payload = {
        "camera_id": active.camera_id,
        "camera_name": active.name,
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
    _log_api_timing("camera/audio/status", started_at)
    return payload


@router.get("/audio/stream-status")
async def camera_audio_stream_status() -> dict[str, object]:
    active = get_camera_source_registry().active_source()
    return {"camera_id": active.camera_id, **get_camera_source_audio_hub("active").status()}


@router.get("/detection-models/status")
async def camera_detection_models_status() -> dict[str, object]:
    started_at = time.perf_counter()
    payload = _camera_detection_models_status()
    _log_api_timing("camera/detection-models/status", started_at)
    return payload


@router.post("/detection-models/enabled")
async def camera_detection_models_enabled(payload: DetectionModelsEnabledRequest) -> dict[str, object]:
    settings = get_settings()
    if payload.fall_detection_enabled is not None:
        settings.fall_detection_enabled = payload.fall_detection_enabled
        _persist_env_value(
            "FALL_DETECTION_ENABLED",
            "true" if payload.fall_detection_enabled else "false",
        )
        fall_service = get_fall_detection_service()
        if payload.fall_detection_enabled:
            await fall_service.start()
        else:
            await fall_service.stop()

    if payload.pose_detection_enabled is not None:
        get_pose_detection_config_service().update(
            {"POSE_DETECTION_ENABLED": payload.pose_detection_enabled}
        )
        pose_service = get_pose_detection_service()
        if payload.pose_detection_enabled:
            await pose_service.start()
        else:
            await pose_service.stop()

    return _camera_detection_models_status()


@router.get("/fall-detection/status")
async def camera_fall_detection_status() -> dict[str, object]:
    started_at = time.perf_counter()
    payload = get_fall_detection_service().status()
    payload["multimodal_review"] = get_fall_multimodal_review_status()
    payload["resolved_target_device_mac"] = get_settings().resolved_fall_detection_target_device_mac
    _log_api_timing("camera/fall-detection/status", started_at)
    return payload


@router.post("/fall-detection/enabled")
async def camera_fall_detection_enabled(payload: DetectionEnabledRequest) -> dict[str, object]:
    settings = get_settings()
    settings.fall_detection_enabled = payload.enabled
    _persist_env_value("FALL_DETECTION_ENABLED", "true" if payload.enabled else "false")
    service = get_fall_detection_service()
    if payload.enabled:
        await service.start()
    else:
        await service.stop()
    status = service.status()
    status["multimodal_review"] = get_fall_multimodal_review_status()
    status["resolved_target_device_mac"] = settings.resolved_fall_detection_target_device_mac
    return {"ok": True, "status": status}


@router.get("/pose-detection/status")
async def camera_pose_detection_status() -> dict[str, object]:
    started_at = time.perf_counter()
    payload = get_pose_detection_service().status()
    _log_api_timing("camera/pose-detection/status", started_at)
    return payload


@router.post("/pose-detection/enabled")
async def camera_pose_detection_enabled(payload: DetectionEnabledRequest) -> dict[str, object]:
    config_service = get_pose_detection_config_service()
    config_service.update({"POSE_DETECTION_ENABLED": payload.enabled})
    service = get_pose_detection_service()
    if payload.enabled:
        await service.start()
    else:
        await service.stop()
    return {"ok": True, "status": service.status()}


@router.get("/pose-detection/latest")
async def camera_pose_detection_latest() -> dict[str, object]:
    started_at = time.perf_counter()
    payload = get_pose_detection_service().latest() or {"status": "empty", "tracks": []}
    _log_api_timing("camera/pose-detection/latest", started_at)
    return payload


@router.post("/analyze-frame")
async def camera_analyze_frame(
    file: UploadFile = File(...),
    session_id: str = "browser-preview",
    pose_enabled: bool = True,
    fall_enabled: bool = True,
) -> dict[str, object]:
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_IMAGE_FORMAT")

    blob = await file.read()
    if len(blob) < 100:
        raise HTTPException(status_code=400, detail="FRAME_IMAGE_REQUIRED")

    try:
        return await get_frame_analysis_worker_service().analyze_frame(
            blob,
            session_id=session_id,
            run_pose=pose_enabled,
            run_fall=fall_enabled,
        )
    except RuntimeError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "pose_latest": {"status": "worker_unavailable", "tracks": []},
            "multimodal_review": get_fall_multimodal_review_status(),
            "worker": get_frame_analysis_worker_service().status(),
        }


@router.post("/analyze-frame/pose")
async def camera_analyze_frame_pose(
    file: UploadFile = File(...),
    session_id: str = "browser-preview",
) -> dict[str, object]:
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_IMAGE_FORMAT")

    blob = await file.read()
    if len(blob) < 100:
        raise HTTPException(status_code=400, detail="FRAME_IMAGE_REQUIRED")

    try:
        return await get_pose_frame_analysis_worker_service().analyze_pose(
            blob,
            session_id=session_id,
        )
    except RuntimeError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "pose_latest": {"status": "worker_unavailable", "tracks": []},
            "worker": get_pose_frame_analysis_worker_service().status(),
        }


@router.post("/analyze-frame/fall")
async def camera_analyze_frame_fall(
    file: UploadFile = File(...),
    session_id: str = "browser-preview",
) -> dict[str, object]:
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_IMAGE_FORMAT")

    blob = await file.read()
    if len(blob) < 100:
        raise HTTPException(status_code=400, detail="FRAME_IMAGE_REQUIRED")

    try:
        return await get_fall_frame_analysis_worker_service().analyze_fall(
            blob,
            session_id=session_id,
        )
    except RuntimeError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "fall": {"ok": False, "status": "worker_unavailable"},
            "multimodal_review": get_fall_multimodal_review_status(),
            "worker": get_fall_frame_analysis_worker_service().status(),
        }


@router.get("/analyze-frame/status")
async def camera_analyze_frame_status() -> dict[str, object]:
    started_at = time.perf_counter()
    payload = {
        "enabled": True,
        "full": get_frame_analysis_worker_service().status(),
        "pose": get_pose_frame_analysis_worker_service().status(),
        "fall": get_fall_frame_analysis_worker_service().status(),
    }
    _log_api_timing("camera/analyze-frame/status", started_at)
    return payload


@router.get("/pose-detection/config")
async def camera_pose_detection_config() -> dict[str, object]:
    return get_pose_detection_config_service().current()


@router.post("/pose-detection/config")
async def camera_pose_detection_config_update(payload: PoseDetectionConfigRequest) -> dict[str, object]:
    config_service = get_pose_detection_config_service()
    updates = {
        key.upper(): value
        for key, value in payload.model_dump(exclude_none=True).items()
    }
    current = config_service.update(updates)
    await get_pose_detection_service().restart()
    return {"ok": True, "config": current, "restarted": True}


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
    image_bytes = get_camera_source_frame_hub("active").latest_frame()
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
        device_mac=settings.resolved_fall_detection_target_device_mac,
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
    active_settings = get_camera_source_settings("active")
    try:
        image_bytes, headers = await asyncio.to_thread(CameraService(active_settings).capture_jpeg)
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
        get_camera_source_frame_hub("active").mjpeg_frames(),
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


@router.get("/stream.pose.mjpg")
async def camera_pose_stream() -> StreamingResponse:
    return StreamingResponse(
        get_camera_pose_frame_hub().mjpeg_frames(),
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
        active = get_camera_source_registry().active_source()
        result = await asyncio.to_thread(CameraService(get_camera_source_settings("active")).ptz_move, payload.direction, payload.mode)
        return {"camera_id": active.camera_id, **result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        code = str(exc)
        status_code = 503
        if code == "CAMERA_NOT_CONFIGURED":
            status_code = 400
        raise HTTPException(status_code=status_code, detail=code) from exc
