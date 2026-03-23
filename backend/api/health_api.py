from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.dependencies import (
    get_community_clusterer,
    get_intelligent_scorer,
    get_stream_service,
    ingest_sample,
)
from backend.models.health_model import HealthSample, HealthTrendPoint, IngestResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_health_sample(payload: HealthSample) -> IngestResponse:
    return await ingest_sample(payload)


@router.get("/realtime/{device_mac}", response_model=HealthSample)
async def get_realtime_sample(device_mac: str) -> HealthSample:
    sample = get_stream_service().latest(device_mac)
    if not sample:
        raise HTTPException(status_code=404, detail="No realtime sample available")
    return sample


@router.get("/trend/{device_mac}", response_model=list[HealthTrendPoint])
async def get_health_trend(
    device_mac: str,
    minutes: int = Query(default=60, ge=5, le=10080),
    limit: int = Query(default=120, ge=10, le=1000),
) -> list[HealthTrendPoint]:
    return get_stream_service().trend(device_mac, minutes=minutes, limit=limit)


@router.get("/community/overview")
async def get_community_overview() -> dict[str, object]:
    samples = get_stream_service().latest_samples()
    history_by_device = get_stream_service().recent_by_devices(minutes=60, per_device_limit=60)
    summary = get_community_clusterer().summarize(samples, history_by_device)
    score = 0.0
    if samples:
        windows = [
            [
                sample.heart_rate,
                sample.temperature,
                sample.blood_oxygen,
                (sample.blood_pressure_pair or (120, 80))[0],
            ]
            for sample in samples
        ]
        score = get_intelligent_scorer().score_sequence(windows)
    return {
        "clusters": summary.clusters,
        "device_count": len(samples),
        "intelligent_anomaly_score": score,
        "trend": summary.trend,
        "risk_heatmap": summary.risk_heatmap,
    }


@router.get("/intelligent/{device_mac}")
async def get_intelligent_device_analysis(device_mac: str) -> dict[str, object]:
    history = get_stream_service().recent_in_window(device_mac, minutes=60, limit=360)
    if not history:
        raise HTTPException(status_code=404, detail="No device history available")
    result = get_intelligent_scorer().infer_device(device_mac, history, now=history[-1].timestamp, force=True)
    if result is None:
        return {"device_mac": device_mac.upper(), "ready": False, "message": "Not enough data for intelligent inference"}
    return {
        "device_mac": device_mac.upper(),
        "ready": True,
        "probability": result.probability,
        "score": result.score,
        "drift_score": result.drift_score,
        "reconstruction_score": result.reconstruction_score,
        "reason": result.reason,
    }
