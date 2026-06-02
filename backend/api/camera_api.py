from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import requests

from backend.config import get_settings
from backend.dependencies import (
    enrich_alarm_context,
    get_alarm_service,
    get_camera_detection_frame_hub,
    get_camera_processed_frame_hub,
    get_camera_pose_frame_hub,
    get_camera_setup_config_service,
    get_camera_source_audio_hub,
    get_camera_source_frame_hub,
    get_camera_source_registry,
    get_camera_source_settings,
    get_target_user_service,
    get_fall_detection_service,
    get_fall_frame_analysis_worker_service,
    get_fall_multimodal_review_status,
    get_latest_fall_decision_debug,
    get_frame_analysis_worker_service,
    get_health_data_repository,
    get_pose_detection_config_service,
    get_pose_detection_service,
    get_pose_frame_analysis_worker_service,
    get_single_frame_fall_state,
    get_single_frame_pose_state,
    get_websocket_manager,
    ingest_fall_detection_event,
    shutdown_camera_source_hubs,
)
from backend.models.alarm_model import AlarmLayer, AlarmPriority, AlarmRecord, AlarmType
from backend.services.camera_service import CameraService


router = APIRouter(prefix="/camera", tags=["camera"])
_processed_auto_prime_lock = asyncio.Lock()
_last_processed_auto_prime_at = 0.0
_last_overlay_fall_alarm_at = 0.0
_last_overlay_fall_alarm_key = ""


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


def _capture_vision_service_latest_frame() -> tuple[bytes, dict[str, str]] | None:
    settings = get_settings()
    if not settings.vision_service_poll_enabled:
        return None
    url = f"{settings.vision_service_base_url.rstrip('/')}/stream/frame/latest"
    params = {
        "camera_id": settings.vision_service_camera_id or "camera_01",
        "source": "display",
    }
    try:
        response = requests.get(url, params=params, timeout=settings.vision_service_timeout_seconds)
        response.raise_for_status()
    except requests.RequestException:
        return None
    if "jpeg" not in response.headers.get("content-type", "").lower():
        return None
    return (
        response.content,
        {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Camera-Source": "vision-service-latest-frame",
        },
    )


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


class FallSimulationRequest(BaseModel):
    scenario: str = "critical"
    fall_score: float | None = None
    track_id: str = "demo-track-1"


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
    fall_status["decision_debug"] = get_latest_fall_decision_debug()
    return {
        "ok": True,
        "fall_detection": fall_status,
        "pose_detection": get_pose_detection_service().status(),
        "frame_analysis": get_frame_analysis_worker_service().status(),
    }


@router.get("/status")
async def camera_status() -> dict[str, object]:
    active = get_camera_source_registry().active_source()
    status = await asyncio.to_thread(CameraService(get_camera_source_settings("active")).check_status)
    return {
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


@router.get("/stream-status")
async def camera_stream_status() -> dict[str, object]:
    active = get_camera_source_registry().active_source()
    raw = get_camera_source_frame_hub("active").status()
    processed_hub = get_camera_processed_frame_hub()
    pose_hub = get_camera_pose_frame_hub()
    detection_hub = get_camera_detection_frame_hub()
    return {
        "camera_id": active.camera_id,
        **raw,
        "processed": processed_hub.status(),
        "processed_overlay": processed_hub.overlay_status() if hasattr(processed_hub, "overlay_status") else {},
        "pose_overlay": pose_hub.overlay_status() if hasattr(pose_hub, "overlay_status") else {},
        "fall_overlay": detection_hub.overlay_status() if hasattr(detection_hub, "overlay_status") else {},
        "fall_decision_debug": get_latest_fall_decision_debug(),
    }


@router.get("/processed-overlay/status")
async def camera_processed_overlay_status() -> dict[str, object]:
    processed_hub = get_camera_processed_frame_hub()
    pose_hub = get_camera_pose_frame_hub()
    detection_hub = get_camera_detection_frame_hub()
    return {
        "ok": True,
        "processed": processed_hub.status(),
        "processed_overlay": processed_hub.overlay_status() if hasattr(processed_hub, "overlay_status") else {},
        "pose_overlay": pose_hub.overlay_status() if hasattr(pose_hub, "overlay_status") else {},
        "fall_overlay": detection_hub.overlay_status() if hasattr(detection_hub, "overlay_status") else {},
        "fall_decision_debug": get_latest_fall_decision_debug(),
        "frame_analysis": get_frame_analysis_worker_service().status(),
        "pose_worker": get_pose_frame_analysis_worker_service().status(),
        "fall_worker": get_fall_frame_analysis_worker_service().status(),
    }


async def _latest_camera_frame_for_overlay() -> bytes:
    frame = get_camera_source_frame_hub("active").latest_frame()
    if frame is None:
        frame = get_camera_processed_frame_hub().latest_frame()
    if frame is None:
        try:
            service = CameraService(get_camera_source_settings("active"))
            if service.uses_runtime_managed_source():
                frame, _headers = await asyncio.to_thread(
                    service.capture_runtime_jpeg_fast,
                    timeout_seconds=0.8,
                )
            else:
                frame, _headers = await asyncio.to_thread(service.capture_jpeg)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=f"CAMERA_FRAME_UNAVAILABLE: {exc}") from exc
    if not frame or len(frame) < 100:
        raise HTTPException(status_code=503, detail="CAMERA_FRAME_UNAVAILABLE")
    return frame


async def _prime_processed_overlay_if_needed(*, include_fall: bool = False) -> None:
    global _last_processed_auto_prime_at
    processed_hub = get_camera_processed_frame_hub()
    if not hasattr(processed_hub, "overlay_status") or not hasattr(processed_hub, "prime_overlay"):
        return
    try:
        overlay_status = processed_hub.overlay_status()
    except Exception:
        overlay_status = {}
    if isinstance(overlay_status, dict) and overlay_status.get("has_renderable_overlay"):
        return
    now = time.monotonic()
    if now - _last_processed_auto_prime_at < 6.0:
        return

    async with _processed_auto_prime_lock:
        now = time.monotonic()
        if now - _last_processed_auto_prime_at < 6.0:
            return
        _last_processed_auto_prime_at = now
        try:
            overlay_status = processed_hub.overlay_status()
        except Exception:
            overlay_status = {}
        if isinstance(overlay_status, dict) and overlay_status.get("has_renderable_overlay"):
            return

    try:
        frame = await _latest_camera_frame_for_overlay()
        now = time.time()
        pose_result = await get_pose_frame_analysis_worker_service().analyze_pose(
            frame,
            session_id="processed-overlay-auto-prime",
        )
        pose_payload: dict[str, object] | None = None
        pose_latest = pose_result.get("pose_latest")
        if isinstance(pose_latest, dict):
            holder = get_single_frame_pose_state()
            holder.clear()
            holder.update(pose_latest)
            holder["_observed_at"] = now
            tracks = pose_latest.get("tracks")
            if isinstance(tracks, list) and tracks:
                pose_payload = dict(holder)

        fall_payload: dict[str, object] | None = None
        if include_fall:
            fall_result = await get_fall_frame_analysis_worker_service().analyze_fall(
                frame,
                session_id="processed-overlay-auto-prime",
            )
            raw_fall = fall_result.get("fall") if isinstance(fall_result.get("fall"), dict) else None
            if isinstance(raw_fall, dict):
                normalized = _fall_payload_for_overlay(raw_fall, frame)
                if normalized:
                    holder = get_single_frame_fall_state()
                    holder.clear()
                    holder.update(normalized)
                    holder["_observed_at"] = now
                    fall_payload = dict(holder)

        processed_hub.prime_overlay(
            pose_payload=pose_payload,
            fall_payload=fall_payload,
        )
    except Exception:
        # Stream endpoints must remain responsive. A failed prime only means the
        # processed stream will show its diagnostic overlay until the next frame
        # analysis succeeds.
        return


@router.post("/processed-overlay/prime")
async def camera_processed_overlay_prime(include_fall: bool = False) -> dict[str, object]:
    """Analyze the latest camera frame once and seed the combined overlay state.

    This endpoint is intentionally explicit: realtime pose/fall services can be
    empty while the camera is still visible. Priming lets the UI validate the
    server-side combined stream with the current frame without waiting for a
    long-running realtime process to publish tracks.
    """
    frame = await _latest_camera_frame_for_overlay()

    now = time.time()
    pose_result = await get_pose_frame_analysis_worker_service().analyze_pose(
        frame,
        session_id="processed-overlay-prime",
    )
    pose_latest = pose_result.get("pose_latest")
    pose_tracks = 0
    pose_seeded = False
    pose_overlay_payload: dict[str, object] | None = None
    if isinstance(pose_latest, dict):
        holder = get_single_frame_pose_state()
        holder.clear()
        holder.update(pose_latest)
        holder["_observed_at"] = now
        tracks = pose_latest.get("tracks")
        pose_tracks = len(tracks) if isinstance(tracks, list) else 0
        pose_seeded = pose_tracks > 0
        pose_overlay_payload = dict(holder)

    fall_result: dict[str, object] = {"ok": False, "status": "skipped", "error": None}
    if include_fall:
        try:
            fall_result = await get_fall_frame_analysis_worker_service().analyze_fall(
                frame,
                session_id="processed-overlay-prime",
            )
        except Exception as exc:
            fall_result = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
    fall_payload = fall_result.get("fall") if isinstance(fall_result.get("fall"), dict) else None
    fall_seeded = False
    normalized: dict[str, object] | None = None
    if isinstance(fall_payload, dict):
        normalized = _fall_payload_for_overlay(fall_payload, frame)
        if normalized:
            holder = get_single_frame_fall_state()
            holder.clear()
            holder.update(normalized)
            holder["_observed_at"] = now
            fall_seeded = bool(normalized.get("bbox"))
            await _maybe_ingest_overlay_fall_alarm(normalized, source="processed-overlay-prime")

    processed_hub = get_camera_processed_frame_hub()
    if hasattr(processed_hub, "prime_overlay"):
        processed_hub.prime_overlay(
            pose_payload=pose_overlay_payload,
            fall_payload=normalized if isinstance(fall_payload, dict) else None,
        )
    # Let async fallback futures settle if a stream consumer already triggered them.
    processed_overlay = processed_hub.overlay_status() if hasattr(processed_hub, "overlay_status") else {}
    return {
        "ok": True,
        "frame_size": len(frame),
        "pose_seeded": pose_seeded,
        "pose_tracks": pose_tracks,
        "fall_seeded": fall_seeded,
        "pose_result": {
            "ok": pose_result.get("ok"),
            "error": pose_result.get("error"),
        },
        "fall_result": {
            "ok": fall_payload.get("ok") if isinstance(fall_payload, dict) else fall_result.get("ok"),
            "status": fall_payload.get("status") if isinstance(fall_payload, dict) else None,
            "error": fall_payload.get("error") if isinstance(fall_payload, dict) else fall_result.get("error"),
        },
        "processed_overlay": processed_overlay,
    }


async def _maybe_ingest_overlay_fall_alarm(
    payload: dict[str, object],
    *,
    source: str,
) -> AlarmRecord | None:
    """Promote a processed-overlay fall payload into the normal alarm pipeline.

    The combined overlay stream already runs the model against the same camera
    frame the family sees. Without this bridge the UI can draw fall-like boxes
    while the family alarm websocket never receives an event. Keep the gate
    narrow so normal tracking boxes do not create false alarms.
    """
    global _last_overlay_fall_alarm_at, _last_overlay_fall_alarm_key

    state = str(payload.get("state") or payload.get("status") or "").strip().lower()
    status = str(payload.get("status") or state).strip().lower()
    try:
        fall_score = float(payload.get("fall_score") or 0.0)
    except (TypeError, ValueError):
        fall_score = 0.0
    fall_detected = bool(payload.get("fall_detected"))

    alarm_like_states = {
        "fall",
        "fallen",
        "confirmed_fall",
        "suspected_fall",
        "possible_fall",
        "fall_detected",
        "abnormal_recovery",
        "needs_assistance",
        "emergency",
        "lying",
    }
    if (
        not fall_detected
        and state not in alarm_like_states
        and status not in alarm_like_states
        and fall_score < 0.18
    ):
        return None

    now = time.monotonic()
    bbox = payload.get("bbox")
    bbox_key = ""
    if isinstance(bbox, list) and len(bbox) >= 4:
        try:
            bbox_key = ",".join(str(int(float(value) // 16)) for value in bbox[:4])
        except (TypeError, ValueError):
            bbox_key = ""
    dedupe_key = f"{source}:{state}:{status}:{round(fall_score, 2)}:{bbox_key}"
    if dedupe_key == _last_overlay_fall_alarm_key and now - _last_overlay_fall_alarm_at < 12:
        return None
    _last_overlay_fall_alarm_key = dedupe_key
    _last_overlay_fall_alarm_at = now

    event_state = state
    if event_state in {"fall", "fallen", "fall_detected"} or fall_detected or fall_score >= 0.55:
        event_state = "confirmed_fall"
    elif event_state in {"lying"} or fall_score >= 0.18:
        event_state = "suspected_fall"
    if event_state in {"normal", "tracked", ""}:
        event_state = "suspected_fall"

    event: dict[str, object] = {
        "source": source,
        "state": event_state,
        "status": status or event_state,
        "event_type": "fall_detected",
        "fall_detected": fall_detected or event_state == "confirmed_fall",
        "fall_score": fall_score,
        "track_id": "overlay-fall-track",
        "bbox": bbox,
        "frame_width": payload.get("frame_width"),
        "frame_height": payload.get("frame_height"),
        "detections": payload.get("detections") if isinstance(payload.get("detections"), list) else [],
        "injury": {
            "level": "I2" if event_state == "confirmed_fall" else "I1",
            "advice": "请立即查看家庭摄像头画面，并确认老人是否跌倒或需要帮助。",
        },
    }
    if event_state == "confirmed_fall":
        event["severity"] = "L2"
    else:
        event["severity"] = "L1"
    return await ingest_fall_detection_event(event)


def _fall_payload_for_overlay(fall_payload: dict[str, object], frame_bytes: bytes) -> dict[str, object] | None:
    try:
        import cv2
        import numpy as np
    except Exception:
        cv2 = None
        np = None

    frame_width = 0
    frame_height = 0
    image = None
    if cv2 is not None and np is not None:
        image = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is not None:
            frame_height, frame_width = image.shape[:2]

    fall_result = fall_payload.get("fall_result") if isinstance(fall_payload.get("fall_result"), dict) else fall_payload
    if not isinstance(fall_result, dict):
        return None
    detections = fall_result.get("detections") if isinstance(fall_result.get("detections"), list) else []
    bbox = _fallback_bbox_from_detections(detections)
    frame_meta = fall_result.get("frame") if isinstance(fall_result.get("frame"), dict) else {}
    frame_width = int(frame_meta.get("width") or frame_width or 0)
    frame_height = int(frame_meta.get("height") or frame_height or 0)
    score = fall_result.get("fall_score")
    if not isinstance(score, (int, float)):
        scores = fall_result.get("scores") if isinstance(fall_result.get("scores"), dict) else {}
        score = scores.get("fall") if isinstance(scores.get("fall"), (int, float)) else 0.0
    payload: dict[str, object] = {
        "status": str(fall_result.get("status") or "normal"),
        "state": str(fall_result.get("status") or "normal"),
        "fall_detected": bool(fall_result.get("fall_detected")),
        "fall_score": float(score or 0.0),
        "detections": detections,
    }
    if frame_width > 0 and frame_height > 0:
        payload["frame_width"] = frame_width
        payload["frame_height"] = frame_height
    if bbox is None and image is not None:
        bbox = _person_bbox_for_overlay(image)
        if bbox is not None and payload["state"] == "normal":
            payload["state"] = "tracked"
            payload["status"] = "tracked"
    if bbox is not None:
        payload["bbox"] = bbox
    return payload


def _person_bbox_for_overlay(image) -> list[float] | None:
    try:
        target_user_service = get_target_user_service()
        boxes = target_user_service._collect_person_boxes(  # type: ignore[attr-defined]
            image,
            target_user_service._fallback_person_model,  # type: ignore[attr-defined]
            allowed_labels={"person", "fall", "fallen", "sitting", "lying", "bending"},
            conf=0.12,
            imgsz=416,
        )
    except Exception:
        boxes = []
    if not boxes:
        return None
    bbox, score, label = max(boxes, key=lambda item: float(item[1] or 0.0))
    try:
        return [float(value) for value in bbox[:4]]
    except Exception:
        return None


def _fallback_bbox_from_detections(detections: object) -> list[float] | None:
    if not isinstance(detections, list):
        return None
    best: tuple[float, list[float]] | None = None
    for item in detections:
        if not isinstance(item, dict):
            continue
        raw_bbox = item.get("bbox")
        if not isinstance(raw_bbox, list) or len(raw_bbox) < 4:
            continue
        try:
            bbox = [float(value) for value in raw_bbox[:4]]
        except (TypeError, ValueError):
            continue
        label = str(item.get("label") or item.get("class_name") or "").lower()
        score = item.get("score")
        try:
            confidence = float(score if score is not None else item.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if "person" in label:
            confidence += 1.0
        if best is None or confidence > best[0]:
            best = (confidence, bbox)
    return best[1] if best is not None else None


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
    frame = get_camera_source_frame_hub("active").latest_frame()
    if frame and len(frame) > 100:
        return Response(
            content=frame,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Camera-Source": "vision-service-frame-cache",
            },
        )
    vision_frame = await asyncio.to_thread(_capture_vision_service_latest_frame)
    if vision_frame is not None:
        image_bytes, headers = vision_frame
        return Response(content=image_bytes, media_type="image/jpeg", headers=headers)
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
    active = get_camera_source_registry().active_source()
    status = await asyncio.to_thread(CameraService(get_camera_source_settings("active")).check_audio_status)
    return {
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


@router.get("/audio/stream-status")
async def camera_audio_stream_status() -> dict[str, object]:
    active = get_camera_source_registry().active_source()
    return {"camera_id": active.camera_id, **get_camera_source_audio_hub("active").status()}


@router.get("/detection-models/status")
async def camera_detection_models_status() -> dict[str, object]:
    return _camera_detection_models_status()


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
    payload = get_fall_detection_service().status()
    payload["multimodal_review"] = get_fall_multimodal_review_status()
    payload["resolved_target_device_mac"] = get_settings().resolved_fall_detection_target_device_mac
    payload["decision_debug"] = get_latest_fall_decision_debug()
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
    return get_pose_detection_service().status()


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
    return get_pose_detection_service().latest() or {"status": "empty", "tracks": []}


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
        result = await get_pose_frame_analysis_worker_service().analyze_pose(
            blob,
            session_id=session_id,
        )
        latest = result.get("pose_latest")
        if isinstance(latest, dict):
            holder = get_single_frame_pose_state()
            holder.clear()
            holder.update(latest)
            holder["_observed_at"] = __import__("time").time()
        return result
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
        result = await get_fall_frame_analysis_worker_service().analyze_fall(
            blob,
            session_id=session_id,
        )
        fall = result.get("fall")
        if isinstance(fall, dict):
            normalized = _fall_payload_for_overlay(fall, blob)
            if isinstance(normalized, dict):
                holder = get_single_frame_fall_state()
                holder.clear()
                holder.update(normalized)
                holder["_observed_at"] = __import__("time").time()
        return result
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
    return {
        "enabled": True,
        "full": get_frame_analysis_worker_service().status(),
        "pose": get_pose_frame_analysis_worker_service().status(),
        "fall": get_fall_frame_analysis_worker_service().status(),
    }


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


def _fall_simulation_event(
    *,
    scenario: str,
    fall_score: float | None,
    track_id: str,
    snapshot_path: str | None,
) -> dict[str, object]:
    normalized = scenario.strip().lower().replace("-", "_")
    now_slug = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base: dict[str, object] = {
        "track_id": track_id.strip() or "demo-track-1",
        "incident_id": f"{track_id.strip() or 'demo-track-1'}-{normalized}-{now_slug}",
        "snapshot_path": snapshot_path,
        "source": "fall_detection_demo",
        "demo": True,
        "scores": {"detector": 0.66, "posture": 0.72, "semantic": 0.38, "hybrid": 0.74},
    }
    if normalized in {"critical", "high", "confirmed_critical", "confirmed_fall_critical"}:
        base.update(
            {
                "event_type": "fall_confirmed",
                "state": "confirmed_fall",
                "severity": "L3",
                "fall_score": fall_score if fall_score is not None else 0.87,
                "injury": {
                    "level": "I3",
                    "reason": "demo_confirmed_fall_critical",
                    "down_seconds": 4.2,
                    "advice": "请立即查看现场并联系护理人员，必要时呼叫急救。",
                },
            }
        )
    elif normalized in {"warning", "confirmed", "confirmed_warning", "confirmed_fall_warning"}:
        base.update(
            {
                "event_type": "fall_confirmed",
                "state": "confirmed_fall",
                "severity": "L2",
                "fall_score": fall_score if fall_score is not None else 0.68,
                "injury": {
                    "level": "I2",
                    "reason": "demo_confirmed_fall_warning",
                    "down_seconds": 2.0,
                    "advice": "请尽快查看现场视频，确认老人能否自主起身。",
                },
            }
        )
    elif normalized in {"notice", "suspected", "suspected_fall", "possible"}:
        base.update(
            {
                "event_type": "fall_suspected",
                "state": "suspected_fall",
                "severity": "L1",
                "fall_score": fall_score if fall_score is not None else 0.32,
                "injury": {
                    "level": "I1",
                    "reason": "demo_suspected_fall",
                    "down_seconds": 1.0,
                    "advice": "请查看现场并等待系统复核结果。",
                },
            }
        )
    elif normalized in {"emergency", "needs_assistance"}:
        base.update(
            {
                "event_type": "fall_followup",
                "state": "emergency",
                "severity": "L4",
                "fall_score": fall_score if fall_score is not None else 0.9,
                "injury": {
                    "level": "I4",
                    "reason": "demo_major_injury_or_emergency_risk",
                    "down_seconds": 45.0,
                    "advice": "请立即安排现场人员协助，避免随意搬动老人，必要时呼叫急救。",
                },
            }
        )
    elif normalized in {"abnormal_recovery", "recovery"}:
        base.update(
            {
                "event_type": "fall_followup",
                "state": "abnormal_recovery",
                "severity": "L3",
                "fall_score": fall_score if fall_score is not None else 0.76,
                "injury": {
                    "level": "I3",
                    "reason": "demo_abnormal_recovery",
                    "down_seconds": 8.0,
                    "advice": "跌倒后恢复异常，请尽快人工确认并准备医疗支援。",
                },
            }
        )
    else:
        base.update(
            {
                "event_type": "fall_suspected",
                "state": "suspected_fall",
                "severity": "L1",
                "fall_score": fall_score if fall_score is not None else 0.24,
                "injury": {
                    "level": "I1",
                    "reason": f"demo_{normalized or 'suspected_fall'}",
                    "down_seconds": 0.9,
                    "advice": "请查看现场并人工确认。",
                },
            }
        )
    return base


@router.post("/fall-detection/simulate")
async def camera_fall_detection_simulate(payload: FallSimulationRequest | None = None) -> AlarmRecord:
    settings = get_settings()
    if not settings.debug and settings.environment != "development":
        raise HTTPException(status_code=404, detail="Not found")
    payload = payload or FallSimulationRequest()

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

    event = _fall_simulation_event(
        scenario=payload.scenario,
        fall_score=payload.fall_score,
        track_id=payload.track_id,
        snapshot_path=snapshot_path,
    )
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
            "severity": event.get("severity"),
            "injury_level": (event.get("injury") or {}).get("level") if isinstance(event.get("injury"), dict) else None,
            "track_id": event.get("track_id"),
            "incident_id": event["incident_id"],
            "is_demo": True,
        },
    )
    return enrich_alarm_context(fallback_alarm)


@router.get("/snapshot")
async def camera_snapshot() -> Response:
    active = get_camera_source_registry().active_source()
    active_settings = get_camera_source_settings(active.camera_id)
    service = CameraService(active_settings)
    frame = get_camera_source_frame_hub("active").latest_frame()
    if frame and len(frame) > 100:
        return Response(
            content=frame,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Camera-Source": "active-stream-cache",
            },
        )
    vision_frame = await asyncio.to_thread(_capture_vision_service_latest_frame)
    if vision_frame is not None:
        image_bytes, headers = vision_frame
        return Response(content=image_bytes, media_type="image/jpeg", headers=headers)
    if active_settings.camera_source_mode == "local":
        frame = get_camera_source_frame_hub("active").latest_frame()
        if frame and len(frame) > 100:
            return Response(
                content=frame,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                    "X-Camera-Source": "local-active-stream-cache",
                },
            )
        try:
            image_bytes, headers = await asyncio.to_thread(service.capture_local_jpeg)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return Response(content=image_bytes, media_type="image/jpeg", headers=headers)
    if service.uses_runtime_managed_source():
        try:
            image_bytes, headers = await asyncio.to_thread(service.capture_runtime_jpeg_fast)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"RUNTIME_SNAPSHOT_UNAVAILABLE: {exc}") from exc
        return Response(content=image_bytes, media_type="image/jpeg", headers=headers)

    try:
        image_bytes, headers = await asyncio.to_thread(service.capture_jpeg)
    except RuntimeError as exc:
        code = str(exc)
        status_code = 503
        if code == "CAMERA_NOT_CONFIGURED":
            status_code = 400
        raise HTTPException(status_code=status_code, detail=code) from exc

    return Response(content=image_bytes, media_type="image/jpeg", headers=headers)


@router.get("/processed-snapshot")
async def camera_processed_snapshot() -> Response:
    asyncio.create_task(_prime_processed_overlay_if_needed(include_fall=False))
    frame = get_camera_processed_frame_hub().latest_frame()
    if frame is None:
        frame = get_camera_source_frame_hub("active").latest_frame()
    if frame is None:
        vision_frame = await asyncio.to_thread(_capture_vision_service_latest_frame)
        if vision_frame is not None:
            image_bytes, headers = vision_frame
            return Response(content=image_bytes, media_type="image/jpeg", headers=headers)
        try:
            frame = await _latest_camera_frame_for_overlay()
        except HTTPException as exc:
            raise exc
    if not frame or len(frame) < 100:
        raise HTTPException(status_code=503, detail="PROCESSED_FRAME_UNAVAILABLE")
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


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


@router.get("/stream.processed.mjpg")
async def camera_processed_stream() -> StreamingResponse:
    asyncio.create_task(_prime_processed_overlay_if_needed(include_fall=False))
    return StreamingResponse(
        get_camera_processed_frame_hub().mjpeg_frames(),
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
