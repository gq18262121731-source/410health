from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress

from fastapi import WebSocket

from backend.config import Settings
from backend.services.camera_service import CameraService


logger = logging.getLogger(__name__)


class CameraFrameHub:
    """Single backend camera reader that fans frames out to many browser clients."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._capture_task: asyncio.Task[None] | None = None
        self._latest_frame: bytes | None = None
        self._latest_frame_at: float | None = None
        self._latest_frame_size = 0
        self._last_error: str | None = None
        self._frames_total = 0
        self._broadcast_total = 0
        self._fps_window_started_at = time.monotonic()
        self._fps_window_frames = 0
        self._source_fps = 0.0
        self._broadcast_fps = 0.0
        self._broadcast_window_started_at = time.monotonic()
        self._broadcast_window_frames = 0
        self._active_url: str | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
            if self._capture_task is None or self._capture_task.done():
                self._capture_task = asyncio.create_task(self._capture_loop())

        if self._latest_frame:
            await self._send_frame(websocket, self._latest_frame)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
            if not self._clients and self._capture_task and not self._capture_task.done():
                self._capture_task.cancel()
                self._capture_task = None

    def status(self) -> dict[str, object]:
        return {
            "clients": len(self._clients),
            "running": bool(self._capture_task and not self._capture_task.done()),
            "latest_frame_at": self._latest_frame_at,
            "latest_frame_size": self._latest_frame_size,
            "last_error": self._last_error,
            "frames_total": self._frames_total,
            "broadcast_total": self._broadcast_total,
            "target_fps": round(max(1.0, min(self._settings.camera_stream_fps, 30.0)), 2),
            "source_fps": round(self._source_fps, 2),
            "broadcast_fps": round(self._broadcast_fps, 2),
            "measured_fps": round(self._source_fps, 2),
            "active_url": self._mask_url(self._active_url),
        }

    async def _capture_loop(self) -> None:
        service = CameraService(self._settings)

        try:
            while True:
                try:
                    await self._run_ffmpeg_stream(service)
                except Exception as exc:  # noqa: BLE001 - keep stream alive for reconnects.
                    self._last_error = f"{exc.__class__.__name__}: {exc}"
                    logger.warning("Camera stream failed, retrying: %s", self._last_error)
                    await self._capture_snapshot_fallback(service)
                    await asyncio.sleep(0.6)
        except asyncio.CancelledError:
            raise

    async def _run_ffmpeg_stream(self, service: CameraService) -> None:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        fps = max(1.0, min(self._settings.camera_stream_fps, 24.0))
        last_error = ""

        for url in service.stream_rtsp_urls:
            async with self._lock:
                if not self._clients:
                    return

            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-probesize",
                "32",
                "-analyzeduration",
                "0",
                "-max_delay",
                "0",
                "-rtsp_transport",
                "tcp",
                "-timeout",
                str(int(self._settings.camera_snapshot_timeout_seconds * 1_000_000)),
                "-i",
                url,
                "-an",
                "-vf",
                f"fps={fps:.2f}",
                "-q:v",
                "8",
                "-f",
                "mjpeg",
                "-",
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            buffer = b""
            frame_count = 0
            last_frame_at = time.monotonic()
            self._active_url = url

            try:
                if process.stdout is None:
                    continue

                while True:
                    async with self._lock:
                        if not self._clients:
                            return

                    try:
                        chunk = await asyncio.wait_for(process.stdout.read(32768), timeout=4.0)
                    except asyncio.TimeoutError:
                        if frame_count == 0 or time.monotonic() - last_frame_at > 4.0:
                            raise RuntimeError("CAMERA_STREAM_READ_TIMEOUT")
                        continue

                    if not chunk:
                        break

                    buffer += chunk
                    while True:
                        start = buffer.find(b"\xff\xd8")
                        end = buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                        if start < 0:
                            buffer = buffer[-2:]
                            break
                        if end < 0:
                            buffer = buffer[start:]
                            break

                        frame = buffer[start : end + 2]
                        buffer = buffer[end + 2 :]
                        frame_count += 1
                        last_frame_at = time.monotonic()
                        self._latest_frame = frame
                        self._latest_frame_at = time.time()
                        self._latest_frame_size = len(frame)
                        self._last_error = None
                        self._record_frame()
                        await self._broadcast_frame(frame)
            finally:
                process.kill()
                with suppress(ProcessLookupError):
                    await asyncio.wait_for(process.wait(), timeout=2.0)

            stderr = b""
            if process.stderr:
                with suppress(Exception):
                    stderr = await asyncio.wait_for(process.stderr.read(), timeout=0.2)
            last_error = stderr.decode("utf-8", errors="replace").strip()
            if frame_count > 0:
                return

        raise RuntimeError(last_error or "CAMERA_STREAM_NO_FRAMES")

    async def _capture_snapshot_fallback(self, service: CameraService) -> None:
        try:
            frame, _headers = await asyncio.to_thread(service.capture_jpeg)
        except Exception:
            return
        self._latest_frame = frame
        self._latest_frame_at = time.time()
        self._latest_frame_size = len(frame)
        self._record_frame()
        await self._broadcast_frame(frame)

    def _record_frame(self) -> None:
        self._frames_total += 1
        self._fps_window_frames += 1
        now = time.monotonic()
        elapsed = now - self._fps_window_started_at
        if elapsed >= 2.0:
            self._source_fps = self._fps_window_frames / elapsed
            self._fps_window_frames = 0
            self._fps_window_started_at = now

    def _record_broadcast(self, count: int) -> None:
        if count <= 0:
            return

        self._broadcast_total += count
        self._broadcast_window_frames += count
        now = time.monotonic()
        elapsed = now - self._broadcast_window_started_at
        if elapsed >= 2.0:
            self._broadcast_fps = self._broadcast_window_frames / elapsed
            self._broadcast_window_frames = 0
            self._broadcast_window_started_at = now

    async def _broadcast_frame(self, frame: bytes) -> None:
        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return

        stale: list[WebSocket] = []
        sent = 0
        for websocket in clients:
            try:
                await self._send_frame(websocket, frame)
                sent += 1
            except Exception:
                stale.append(websocket)

        self._record_broadcast(sent)

        if stale:
            async with self._lock:
                for websocket in stale:
                    self._clients.discard(websocket)

    @staticmethod
    async def _send_frame(websocket: WebSocket, frame: bytes) -> None:
        await websocket.send_bytes(frame)

    def _mask_url(self, url: str | None) -> str | None:
        if not url:
            return None
        password = self._settings.camera_password
        return url.replace(password, "***") if password else url
