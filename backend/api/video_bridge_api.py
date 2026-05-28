from __future__ import annotations

from fastapi import APIRouter

from backend.dependencies import get_video_bridge_service
from backend.models.video_bridge_model import (
    VideoAnalysisIngestResponse,
    VideoAnalysisPushRequest,
    VideoBridgeStatusResponse,
)


router = APIRouter(prefix="/video-bridge", tags=["video-bridge"])


@router.post("/analysis", response_model=VideoAnalysisIngestResponse)
async def receive_video_analysis(payload: VideoAnalysisPushRequest) -> VideoAnalysisIngestResponse:
    """Receive telemetry pushed by a future standalone video analysis service."""

    return get_video_bridge_service().ingest(payload)


@router.get("/status", response_model=VideoBridgeStatusResponse)
async def get_video_bridge_status() -> VideoBridgeStatusResponse:
    """Return bridge status for frontend placeholder and future service checks."""

    return get_video_bridge_service().status()
