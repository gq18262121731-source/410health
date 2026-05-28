from __future__ import annotations

from datetime import datetime, timezone

from backend.models.video_bridge_model import (
    VideoAnalysisIngestResponse,
    VideoAnalysisPushRequest,
    VideoBridgeStatusResponse,
)
from backend.services.video_adapter import ADAPTER_VERSION, VideoAnalysisAdapter


class VideoBridgeService:
    """In-memory bridge for future standalone video analysis service pushes."""

    def __init__(self, adapter: VideoAnalysisAdapter | None = None) -> None:
        self._adapter = adapter or VideoAnalysisAdapter()
        self._records: dict[tuple[str, str], object] = {}
        self._updated_at = datetime.now(timezone.utc)

    def ingest(self, payload: VideoAnalysisPushRequest) -> VideoAnalysisIngestResponse:
        record = self._adapter.normalize(payload)
        self._records[(record.camera_id, record.stream_name)] = record
        self._updated_at = record.received_at
        return VideoAnalysisIngestResponse(
            camera_id=record.camera_id,
            stream_name=record.stream_name,
            received_at=record.received_at,
            service_state=record.service_state,
            stale=record.stale,
        )

    def status(self, *, include_mock: bool = True) -> VideoBridgeStatusResponse:
        records = list(self._records.values())
        if not records and include_mock:
            records = [self._adapter.mock_record()]

        records.sort(key=lambda item: item.received_at, reverse=True)
        latest = records[0] if records else None
        bridge_state = latest.service_state if latest else "unknown"
        if records and any(item.service_state in {"error", "degraded"} for item in records):
            bridge_state = "degraded"

        return VideoBridgeStatusResponse(
            bridge_state=bridge_state,
            adapter_version=ADAPTER_VERSION,
            camera_count=len(records),
            updated_at=self._updated_at,
            latest=latest,
            cameras=records,
            notes=[
                "Main-system video bridge is reserved for standalone video-service telemetry.",
                "This bridge does not open RTSP, mutate websocket video streams, run detection, or create alarms.",
            ],
        )
