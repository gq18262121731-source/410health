from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_runtime
from app.core.runtime import Runtime
from app.schemas.stream import StreamControlResponse, StreamStartRequest, StreamStopRequest

router = APIRouter(tags=["stream"])


@router.post("/stream/start", response_model=StreamControlResponse)
def start_stream(
    request: StreamStartRequest,
    runtime: Runtime = Depends(get_runtime),
) -> StreamControlResponse:
    try:
        created, message = runtime.stream_service.start(request.camera_id, request.rtsp_url)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return StreamControlResponse(
        camera_id=request.camera_id,
        status="started" if created else "running",
        message=message,
    )


@router.post("/stream/stop", response_model=StreamControlResponse)
def stop_stream(
    request: StreamStopRequest,
    runtime: Runtime = Depends(get_runtime),
) -> StreamControlResponse:
    stopped = runtime.stream_service.stop(request.camera_id)
    return StreamControlResponse(
        camera_id=request.camera_id,
        status="stopped" if stopped else "not_found",
        message="stream stopped" if stopped else "stream was not running",
    )

