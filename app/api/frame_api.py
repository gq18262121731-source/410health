from __future__ import annotations

import asyncio

import cv2
from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect

from app.api.deps import get_runtime
from app.core.runtime import Runtime

router = APIRouter(prefix="/stream/frame", tags=["stream-frame"])
ws_router = APIRouter(tags=["stream-frame"])


@router.get("/latest")
def latest_frame(
    camera_id: str = "camera_01",
    source: str = Query(default="display", pattern="^(display|main|analysis)$"),
    quality: int = Query(default=70, ge=30, le=90),
    max_age_ms: int = Query(default=3000, ge=100, le=30000),
    runtime: Runtime = Depends(get_runtime),
) -> Response:
    stream_runtime = runtime.source_manager.get_runtime(camera_id)
    if stream_runtime is None:
        raise HTTPException(status_code=404, detail=f"camera not found: {camera_id}")

    buffer, stream_state, display_source = _select_buffer_and_state(runtime, camera_id, source)
    if buffer is None:
        raise HTTPException(status_code=404, detail=f"frame source not available: {source}")

    packet = buffer.latest()
    if packet is None:
        raise HTTPException(status_code=503, detail="no frame available yet")

    frame_age_ms = packet.age_ms
    if frame_age_ms > max_age_ms or stream_state != "connected":
        raise HTTPException(
            status_code=503,
            detail={
                "message": "latest frame is stale",
                "frame_age_ms": frame_age_ms,
                "stream_state": stream_state,
            },
            headers=_frame_headers(
                camera_id=camera_id,
                packet=packet,
                stream_state=stream_state,
                display_source=display_source,
                source=source,
                stale=True,
            ),
        )

    encoded = _encode_jpeg(packet, quality)
    return Response(
        content=encoded,
        media_type="image/jpeg",
        headers=_frame_headers(
            camera_id=camera_id,
            packet=packet,
            stream_state=stream_state,
            display_source=display_source,
            source=source,
        ),
    )


@ws_router.websocket("/ws/frames")
async def ws_frames(
    websocket: WebSocket,
    camera_id: str = "camera_01",
    source: str = Query(default="display", pattern="^(display|main|analysis)$"),
    fps: float = Query(default=5.0, gt=0, le=8),
    quality: int = Query(default=70, ge=30, le=90),
    max_age_ms: int = Query(default=3000, ge=100, le=30000),
) -> None:
    await websocket.accept()
    runtime: Runtime = websocket.app.state.runtime
    frame_interval_sec = 1.0 / min(max(fps, 0.1), 8.0)
    last_seq = -1

    try:
        while True:
            stream_runtime = runtime.source_manager.get_runtime(camera_id)
            if stream_runtime is None:
                await websocket.close(code=1008, reason=f"camera not found: {camera_id}")
                return

            buffer, stream_state, _display_source = _select_buffer_and_state(runtime, camera_id, source)
            if buffer is None:
                await websocket.close(code=1008, reason=f"frame source not available: {source}")
                return

            packet = buffer.latest()
            if (
                packet is not None
                and packet.seq != last_seq
                and packet.age_ms <= max_age_ms
                and stream_state == "connected"
            ):
                await websocket.send_bytes(_encode_jpeg(packet, quality))
                last_seq = packet.seq

            await asyncio.sleep(frame_interval_sec)
    except WebSocketDisconnect:
        return
    except RuntimeError:
        return


def _select_buffer_and_state(runtime: Runtime, camera_id: str, source: str):
    source_manager = runtime.source_manager
    stream_runtime = source_manager.get_runtime(camera_id)
    display_source = "single"
    if stream_runtime is not None:
        display_source, _ = source_manager.display_state(camera_id)

    if source == "analysis":
        status = source_manager.analysis_worker_status(camera_id)
        return source_manager.get_analysis_buffer(camera_id), _state(status), display_source

    if source == "main":
        status = source_manager.main_worker_status(camera_id)
        return source_manager.get_main_buffer(camera_id), _state(status), display_source

    status = (
        source_manager.analysis_worker_status(camera_id)
        if display_source == "analysis"
        else source_manager.main_worker_status(camera_id)
    )
    return source_manager.get_display_buffer(camera_id), _state(status), display_source


def _state(status) -> str:
    return getattr(status, "stream_state", None) or "unknown"


def _encode_jpeg(packet, quality: int) -> bytes:
    ok, encoded = cv2.imencode(".jpg", packet.frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise HTTPException(status_code=500, detail="jpeg encode failed")
    return encoded.tobytes()


def _frame_headers(
    *,
    camera_id: str,
    packet,
    stream_state: str,
    display_source: str,
    source: str,
    stale: bool = False,
) -> dict[str, str]:
    headers = {
        "X-Camera-Id": camera_id,
        "X-Frame-Seq": str(packet.seq),
        "X-Frame-Age-Ms": str(packet.age_ms),
        "X-Frame-Width": str(packet.width),
        "X-Frame-Height": str(packet.height),
        "X-Stream-State": stream_state or "unknown",
        "X-Display-Source": display_source,
        "X-Frame-Source": source,
        "X-Captured-At": packet.captured_at_iso,
        "Cache-Control": "no-store",
    }
    if stale:
        headers["X-Frame-Stale"] = "true"
    return headers
