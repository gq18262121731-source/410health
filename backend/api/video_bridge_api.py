from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
import requests

from backend.config import get_settings
from backend.dependencies import (
    get_video_bridge_service,
    ingest_fall_detection_event,
)
from backend.models.alarm_model import AlarmRecord
from backend.models.video_bridge_model import (
    VideoBridgeFallAlarmSimulationRequest,
    VideoBridgeFallAlarmSimulationResponse,
    VideoBridgeFallEventRequest,
    VideoBridgeFallEventResponse,
    VideoAnalysisIngestResponse,
    VideoAnalysisPushRequest,
    VideoBridgeStatusResponse,
    VisionStreamProbeRequest,
    VisionStreamSwitchHostRequest,
)


router = APIRouter(prefix="/video-bridge", tags=["video-bridge"])


def _clamp_probability(value: float | None, *, default: float = 0.91) -> float:
    if value is None:
        value = default
    return max(0.0, min(1.0, float(value)))


def _fall_alarm_elder_id(alarm: AlarmRecord) -> str:
    return str(alarm.metadata.get("elder_id") or get_settings().fall_detection_target_elder_id or "")


def _fall_alarm_elder_name(alarm: AlarmRecord) -> str:
    return str(alarm.metadata.get("elder_name") or "")


@router.post("/analysis", response_model=VideoAnalysisIngestResponse)
async def receive_video_analysis(payload: VideoAnalysisPushRequest) -> VideoAnalysisIngestResponse:
    """Receive telemetry pushed by a future standalone video analysis service."""

    return get_video_bridge_service().ingest(payload)


@router.get("/status", response_model=VideoBridgeStatusResponse)
async def get_video_bridge_status() -> VideoBridgeStatusResponse:
    """Return bridge status for frontend placeholder and future service checks."""

    return get_video_bridge_service().status()


@router.post("/vision/poll-once")
async def poll_vision_service_once() -> dict[str, object]:
    """Pull one health/source/latest cycle from the standalone vision service."""

    return get_video_bridge_service().poll_once()


@router.get("/vision/health")
async def get_vision_service_health() -> object:
    try:
        return get_video_bridge_service().get_vision_health()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"VISION_SERVICE_UNAVAILABLE: {exc}") from exc


@router.get("/vision/source")
async def get_vision_service_source(camera_id: str | None = None) -> object:
    try:
        return get_video_bridge_service().get_vision_source(camera_id)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"VISION_SERVICE_SOURCE_UNAVAILABLE: {exc}") from exc


@router.get("/vision/latest")
async def get_vision_service_latest(camera_id: str | None = None) -> object:
    try:
        return get_video_bridge_service().get_vision_latest(camera_id)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"VISION_SERVICE_RESULTS_UNAVAILABLE: {exc}") from exc


@router.post("/vision/probe")
async def probe_vision_stream(payload: VisionStreamProbeRequest) -> object:
    try:
        return get_video_bridge_service().probe_vision_stream(payload.model_dump(mode="json"))
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"VISION_SERVICE_PROBE_FAILED: {exc}") from exc


@router.post("/vision/switch-host")
async def switch_vision_host(payload: VisionStreamSwitchHostRequest) -> object:
    try:
        return get_video_bridge_service().switch_vision_host(payload.model_dump(mode="json"))
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"VISION_SERVICE_SWITCH_FAILED: {exc}") from exc


@router.post("/fall-events", response_model=VideoBridgeFallEventResponse)
async def receive_video_bridge_fall_event(payload: VideoBridgeFallEventRequest) -> VideoBridgeFallEventResponse:
    """Receive confirmed fall events from the standalone video demo/service."""

    now = datetime.now(timezone.utc)
    timestamp_slug = now.strftime("%Y%m%d%H%M%S%f")
    camera_id = payload.camera_id.strip()
    stream_name = payload.stream_name.strip() or "primary"
    fall_prob = _clamp_probability(
        payload.fall_score if payload.fall_score is not None else payload.fall_prob
    )
    risk = payload.risk
    severity = (payload.severity or "").strip().upper()
    if not severity:
        severity = "L3" if risk in {"high", "critical"} or fall_prob >= 0.82 else "L2"

    snapshot_url = (
        (payload.snapshot_url or "").strip()
        or (payload.snapshot_path or "").strip()
        or "/api/v1/camera/processed-snapshot"
    )
    track_id = (payload.track_id or "").strip() or f"video-bridge-{camera_id}-{timestamp_slug}"
    incident_id = (payload.incident_id or "").strip() or f"video-bridge-fall-{camera_id}-{timestamp_slug}"

    event = payload.model_dump(mode="json", exclude_none=True)
    event.update(
        {
            "source": (payload.source or "vision_service").strip() or "vision_service",
            "demo": bool(payload.demo),
            "event_type": (payload.event_type or "fall_confirmed").strip() or "fall_confirmed",
            "state": (payload.state or "confirmed_fall").strip() or "confirmed_fall",
            "status": (payload.status or payload.state or "confirmed_fall").strip(),
            "severity": severity,
            "risk": risk,
            "risk_level": payload.risk_level or risk,
            "fall_detected": bool(payload.fall_detected),
            "fall_score": fall_prob,
            "fall_prob": fall_prob,
            "camera_id": camera_id,
            "stream_name": stream_name,
            "service_state": payload.service_state,
            "track_id": track_id,
            "incident_id": incident_id,
            "snapshot_url": snapshot_url,
            "snapshot_path": snapshot_url,
            "timestamp": payload.timestamp.isoformat(),
        }
    )

    scores = dict(payload.scores) if isinstance(payload.scores, dict) else {}
    scores.setdefault("video_bridge", fall_prob)
    scores.setdefault("detector", fall_prob)
    scores.setdefault("posture", max(0.72, fall_prob))
    scores.setdefault("hybrid", fall_prob)
    event["scores"] = scores

    injury = dict(payload.injury) if isinstance(payload.injury, dict) else {}
    injury.setdefault("level", "I3" if severity == "L3" else "I2")
    injury.setdefault("reason", "video_bridge_fall_event")
    injury.setdefault("down_seconds", 4.2)
    injury.setdefault("advice", "Please inspect the live camera view immediately and confirm the elder's condition.")
    event["injury"] = injury

    metadata = dict(payload.metadata) if isinstance(payload.metadata, dict) else {}
    metadata.setdefault("trigger", "video_bridge_fall_events")
    metadata.setdefault("received_at", now.isoformat())
    event["metadata"] = metadata

    alarm: AlarmRecord | None = await ingest_fall_detection_event(event)
    if alarm is None:
        raise HTTPException(status_code=409, detail="VIDEO_BRIDGE_FALL_EVENT_NOT_CREATED")

    return VideoBridgeFallEventResponse(
        alarm_id=alarm.id,
        alarm_type=alarm.alarm_type.value,
        alarm=alarm,
        camera_id=camera_id,
        stream_name=stream_name,
        risk=risk,
        fall_prob=fall_prob,
        triggered_at=now,
        elder_id=_fall_alarm_elder_id(alarm),
        elder_name=_fall_alarm_elder_name(alarm),
    )


@router.post("/simulate-fall-alarm", response_model=VideoBridgeFallAlarmSimulationResponse)
async def simulate_video_bridge_fall_alarm(
    payload: VideoBridgeFallAlarmSimulationRequest | None = None,
) -> VideoBridgeFallAlarmSimulationResponse:
    """Promote the latest bridge snapshot into the normal fall-alarm pipeline.

    This is a manual demo hook only. It does not run fall detection, open RTSP,
    mutate video streams, or change the existing alarm flow. A future video
    service can reuse the same event shape when automatic fall results are ready.
    """

    payload = payload or VideoBridgeFallAlarmSimulationRequest()
    status = get_video_bridge_service().status()
    latest = status.latest
    if latest is None:
        raise HTTPException(status_code=404, detail="VIDEO_BRIDGE_STATUS_EMPTY")
    latest_json = latest.model_dump(mode="json")

    settings = get_settings()
    now = datetime.now(timezone.utc)
    fall_prob = payload.fall_prob if payload.fall_prob is not None else latest.fall_prob
    fall_prob = _clamp_probability(fall_prob)
    camera_id = (payload.camera_id or latest.camera_id).strip() or latest.camera_id
    stream_name = (payload.stream_name or latest.stream_name).strip() or latest.stream_name
    snapshot_url = (
        (payload.snapshot_url or "").strip()
        or (latest.snapshot_url or "").strip()
        or "/api/v1/camera/processed-snapshot"
    )
    track_seed = (payload.track_id or latest.track_id or "video-bridge-demo").strip() or "video-bridge-demo"
    track_id = f"{track_seed}-{now.strftime('%Y%m%d%H%M%S%f')}"
    incident_id = f"video-bridge-fall-{camera_id}-{now.strftime('%Y%m%d%H%M%S%f')}"

    event: dict[str, object] = {
        "source": "video_bridge_manual_simulation",
        "demo": True,
        "event_type": "fall_confirmed",
        "state": "confirmed_fall",
        "status": "manual_simulated_fall",
        "severity": "L3",
        "risk": "high",
        "risk_level": "high",
        "fall_detected": True,
        "fall_score": fall_prob,
        "fall_prob": fall_prob,
        "camera_id": camera_id,
        "stream_name": stream_name,
        "service_state": latest.service_state,
        "track_id": track_id,
        "incident_id": incident_id,
        "bbox": latest_json.get("bbox"),
        "target": latest_json.get("target"),
        "snapshot_url": snapshot_url,
        "snapshot_path": snapshot_url,
        "timestamp": now.isoformat(),
        "scores": {
            "video_bridge": fall_prob,
            "detector": fall_prob,
            "posture": max(0.72, fall_prob),
            "hybrid": fall_prob,
        },
        "injury": {
            "level": "I3",
            "reason": "video_bridge_manual_demo",
            "down_seconds": 4.2,
            "advice": "Please inspect the live camera view immediately and confirm the elder's condition.",
        },
        "metadata": {
            "trigger": "manual_video_bridge_button",
            "bridge_adapter_version": latest.adapter_version,
            "stream_url": latest.stream_url,
        },
    }

    alarm: AlarmRecord | None = await ingest_fall_detection_event(event)
    if alarm is None:
        raise HTTPException(status_code=409, detail="VIDEO_BRIDGE_FALL_ALARM_NOT_CREATED")

    return VideoBridgeFallAlarmSimulationResponse(
        alarm=alarm,
        camera_id=camera_id,
        stream_name=stream_name,
        risk="high",
        fall_prob=fall_prob,
        snapshot_url=snapshot_url,
        triggered_at=now,
        elder_id=str(alarm.metadata.get("elder_id") or settings.fall_detection_target_elder_id or ""),
        elder_name=_fall_alarm_elder_name(alarm),
    )
