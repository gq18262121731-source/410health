from __future__ import annotations

import socket
import time

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_runtime
from app.camera.source_models import mask_source_url
from app.core.runtime import Runtime
from app.schemas.stream import (
    StreamControlResponse,
    StreamHostSwitchRequest,
    StreamProbeRequest,
    StreamProbeResponse,
    StreamRuntimeSourceResponse,
    StreamStartRequest,
    StreamStopRequest,
)

router = APIRouter(tags=["stream"])


@router.post("/stream/start", response_model=StreamControlResponse)
def start_stream(
    request: StreamStartRequest,
    runtime: Runtime = Depends(get_runtime),
) -> StreamControlResponse:
    try:
        created, message = runtime.stream_service.start(
            request.camera_id,
            request.rtsp_url,
            main_source_url=request.main_rtsp_url,
            analysis_source_url=request.analysis_rtsp_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    stream_runtime = runtime.source_manager.get_runtime(request.camera_id)
    return StreamControlResponse(
        camera_id=request.camera_id,
        status="restarted",
        message=message,
        main_rtsp_url=stream_runtime.config.main_source_url if stream_runtime else None,
        analysis_rtsp_url=stream_runtime.config.analysis_source_url if stream_runtime else None,
    )


@router.get("/stream/source", response_model=StreamRuntimeSourceResponse)
def stream_source(
    camera_id: str = "camera_01",
    runtime: Runtime = Depends(get_runtime),
) -> StreamRuntimeSourceResponse:
    stream_runtime = runtime.source_manager.get_runtime(camera_id)
    if stream_runtime is None:
        return StreamRuntimeSourceResponse(
            camera_id=camera_id,
            running=False,
            dual_stream_enabled=False,
            display_source_current="none",
            display_fallback_active=False,
            message="camera is not running",
        )

    main_status = stream_runtime.main_worker.status() if stream_runtime.main_worker else None
    analysis_status = stream_runtime.analysis_worker.status() if stream_runtime.analysis_worker else None
    display_source_current, display_fallback_active = runtime.source_manager.display_state(camera_id)
    return StreamRuntimeSourceResponse(
        camera_id=camera_id,
        running=True,
        dual_stream_enabled=stream_runtime.dual_stream_enabled,
        display_source_current=display_source_current,
        display_fallback_active=display_fallback_active,
        main_rtsp_url_masked=mask_source_url(
            stream_runtime.main_config.source_url if stream_runtime.main_config else None
        ),
        analysis_rtsp_url_masked=mask_source_url(
            stream_runtime.analysis_config.source_url if stream_runtime.analysis_config else None
        ),
        main_stream_state=main_status.stream_state if main_status else None,
        analysis_stream_state=analysis_status.stream_state if analysis_status else None,
        main_connected=main_status.connected if main_status else None,
        analysis_connected=analysis_status.connected if analysis_status else None,
        main_frame_age_ms=main_status.frame_age_ms if main_status else None,
        analysis_frame_age_ms=analysis_status.frame_age_ms if analysis_status else None,
        main_capture_fps=main_status.capture_fps if main_status else None,
        analysis_capture_fps=analysis_status.capture_fps if analysis_status else None,
    )


@router.post("/stream/switch-host", response_model=StreamControlResponse)
def switch_stream_host(
    request: StreamHostSwitchRequest,
    runtime: Runtime = Depends(get_runtime),
) -> StreamControlResponse:
    main_rtsp_url = _build_rtsp_url(
        scheme=request.scheme,
        username=request.username,
        password=request.password,
        host=request.host,
        port=request.port,
        path=request.main_path,
    )
    analysis_rtsp_url = _build_rtsp_url(
        scheme=request.scheme,
        username=request.username,
        password=request.password,
        host=request.host,
        port=request.port,
        path=request.analysis_path,
    )
    try:
        _, message = runtime.stream_service.start(
            request.camera_id,
            analysis_rtsp_url,
            main_source_url=main_rtsp_url,
            analysis_source_url=analysis_rtsp_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return StreamControlResponse(
        camera_id=request.camera_id,
        status="restarted",
        message=message,
        main_rtsp_url=mask_source_url(main_rtsp_url),
        analysis_rtsp_url=mask_source_url(analysis_rtsp_url),
    )


@router.post("/stream/probe", response_model=StreamProbeResponse)
def probe_stream_host(request: StreamProbeRequest) -> StreamProbeResponse:
    started = time.monotonic()
    try:
        with socket.create_connection(
            (request.host, request.port),
            timeout=request.timeout_ms / 1000,
        ):
            elapsed_ms = round((time.monotonic() - started) * 1000, 2)
            return StreamProbeResponse(
                host=request.host,
                port=request.port,
                reachable=True,
                elapsed_ms=elapsed_ms,
            )
    except OSError as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        return StreamProbeResponse(
            host=request.host,
            port=request.port,
            reachable=False,
            elapsed_ms=elapsed_ms,
            error=str(exc),
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


def _build_rtsp_url(
    *,
    scheme: str,
    username: str,
    password: str,
    host: str,
    port: int,
    path: str,
) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{scheme}://{username}:{password}@{host}:{port}{normalized_path}"
