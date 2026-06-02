from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_runtime
from app.core.runtime import Runtime
from app.schemas.integration import (
    ManualFallEventRequest,
    ManualFallEventResponse,
    ResultPullListResponse,
    ResultPullResponse,
)
from app.schemas.vision_result import DetectedObject, VisionResult
from app.services.video_bridge_publisher_service import VideoBridgePostError

router = APIRouter(prefix="/integration", tags=["integration"])


@router.get("/results/latest", response_model=ResultPullListResponse)
def latest_results(runtime: Runtime = Depends(get_runtime)) -> ResultPullListResponse:
    results = runtime.realtime_store.all_latest_published()
    return ResultPullListResponse(
        count=len(results),
        results=results,
    )


@router.get("/results/{camera_id}/latest", response_model=ResultPullResponse)
def latest_result_by_camera(
    camera_id: str,
    runtime: Runtime = Depends(get_runtime),
) -> ResultPullResponse:
    runtime_exists = any(
        runtime_item.config.camera_id == camera_id
        for runtime_item in runtime.source_manager.list_runtimes()
    )
    result = runtime.realtime_store.latest_published(camera_id)
    if result is None and not runtime_exists:
        raise HTTPException(status_code=404, detail=f"camera not found: {camera_id}")
    if result is None:
        return ResultPullResponse(
            camera_id=camera_id,
            has_result=False,
            message="camera exists but no published result yet",
        )
    return ResultPullResponse(
        camera_id=camera_id,
        has_result=True,
        result=result,
    )


@router.post("/video-bridge/fall-events/manual", response_model=ManualFallEventResponse)
def trigger_manual_fall_event(
    event: ManualFallEventRequest,
    http_request: Request,
    runtime: Runtime = Depends(get_runtime),
) -> ManualFallEventResponse:
    if runtime.video_bridge_publisher_service is None:
        raise HTTPException(status_code=503, detail="video bridge publisher is not available")

    payload = _build_manual_fall_event_payload(event, http_request, runtime)
    try:
        upstream = runtime.video_bridge_publisher_service.post_fall_event(payload)
    except VideoBridgePostError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "main system rejected fall event",
                "upstream_status_code": exc.status_code,
                "main_system_url": runtime.settings.video_bridge_fall_event_url,
                "body": exc.body,
                "payload": payload,
            },
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "main system fall event endpoint is unreachable",
                "main_system_url": runtime.settings.video_bridge_fall_event_url,
                "error": str(exc),
                "payload": payload,
            },
        ) from exc

    body = upstream.get("body")
    body_dict = body if isinstance(body, dict) else {}
    ok = _bool_or_default(body_dict.get("ok"), True)
    accepted = _bool_or_default(body_dict.get("accepted"), True)
    return ManualFallEventResponse(
        ok=ok,
        accepted=accepted,
        forwarded=True,
        alarm_id=_str_or_none(body_dict.get("alarm_id")),
        alarm_type=_str_or_none(body_dict.get("alarm_type")),
        device_mac=_str_or_none(body_dict.get("device_mac")),
        pushed=_bool_or_none(body_dict.get("pushed")),
        upstream_status_code=upstream.get("status_code"),
        main_system_url=runtime.settings.video_bridge_fall_event_url,
        payload=payload,
        main_system_response=body,
    )


def _build_manual_fall_event_payload(
    event: ManualFallEventRequest,
    http_request: Request,
    runtime: Runtime,
) -> dict[str, Any]:
    result = runtime.realtime_store.latest_published(event.camera_id)
    target = _select_target(result)
    timestamp = event.timestamp or _now_china_iso()
    fall_prob = _clamp_probability(event.fall_prob if event.fall_prob is not None else _target_fall_prob(target))
    if fall_prob is None:
        fall_prob = 0.91
    fall_score = _clamp_probability(event.fall_score)
    if fall_score is None:
        fall_score = fall_prob

    metadata = {
        "trigger": "video_demo_button",
        "operator": "manual_test",
    }
    metadata.update(event.metadata or {})
    if result is not None:
        metadata.update(
            {
                "vision_frame_seq": result.frame_seq,
                "vision_timestamp": result.timestamp,
                "display_source": result.display_source,
                "analysis_source": result.analysis_source,
            }
        )

    return {
        "camera_id": event.camera_id,
        "stream_name": event.stream_name,
        "source": event.source,
        "event_type": event.event_type,
        "state": event.state,
        "risk": event.risk,
        "fall_prob": fall_prob,
        "fall_score": fall_score,
        "track_id": event.track_id or _target_track_id(target) or "demo-track-001",
        "incident_id": event.incident_id or _incident_id(event.camera_id, timestamp),
        "bbox": event.bbox or (target.bbox if target is not None else [120, 80, 420, 520]),
        "snapshot_url": event.snapshot_url or _snapshot_url(http_request, event.camera_id),
        "timestamp": timestamp,
        "demo": event.demo,
        "metadata": metadata,
    }


def _select_target(result: VisionResult | None) -> DetectedObject | None:
    if result is None or not result.objects:
        return None
    targets = [item for item in result.objects if item.is_target]
    if targets:
        return targets[0]
    tracked = [item for item in result.objects if item.track_id is not None]
    if tracked:
        return tracked[0]
    return result.objects[0]


def _target_track_id(target: DetectedObject | None) -> str | None:
    if target is None or target.track_id is None:
        return None
    return str(target.track_id)


def _target_fall_prob(target: DetectedObject | None) -> float | None:
    if target is None or not target.temporal:
        return None
    return _clamp_probability(target.temporal.get("fall_probability"))


def _snapshot_url(http_request: Request, camera_id: str) -> str:
    base_url = str(http_request.base_url).rstrip("/")
    query = urlencode({"camera_id": camera_id, "source": "analysis"})
    return f"{base_url}/stream/frame/latest?{query}"


def _incident_id(camera_id: str, timestamp: str) -> str:
    compact = "".join(ch for ch in timestamp if ch.isdigit())
    return f"video-demo-{compact[:14]}-{camera_id}"


def _now_china_iso() -> str:
    china_tz = timezone(timedelta(hours=8))
    return datetime.now(china_tz).isoformat(timespec="seconds")


def _clamp_probability(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return max(0.0, min(1.0, round(float(value), 4)))
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _bool_or_default(value: Any, default: bool) -> bool:
    parsed = _bool_or_none(value)
    return default if parsed is None else parsed
