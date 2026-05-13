from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from typing import Any, AsyncGenerator, Callable

from fastapi import WebSocket

from backend.config import Settings
from backend.services.camera_service import CameraService


logger = logging.getLogger(__name__)


class CameraFrameHub:
    """Single backend camera reader that fans frames out to many clients."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._clients: set[WebSocket] = set()
        self._mjpeg_clients = 0
        self._lock = asyncio.Lock()
        self._frame_event = asyncio.Event()
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
        self._keep_warm = False
        self._last_broadcasted_at = 0.0
        # 优化2: 帧缓存机制 - 避免重复请求，提高响应速度
        self._frame_cache: dict[str, tuple[bytes, float]] = {}  # key: cache_key, value: (frame, timestamp)
        self._frame_cache_ttl = 0.15  # 缓存150ms，适合6fps
        self._cache_hits = 0
        self._cache_misses = 0

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        stale_clients: list[WebSocket] = []
        async with self._lock:
            stale_clients = [client for client in self._clients if client is not websocket]
            self._clients = {websocket}
            self._ensure_capture_task()

        for stale in stale_clients:
            with suppress(Exception):
                await stale.close(code=4000, reason="superseded_by_new_camera_viewer")

        if self._latest_frame:
            await self._send_frame(websocket, self._latest_frame)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
            self._stop_capture_task_if_idle()

    async def start_keep_warm(self) -> None:
        async with self._lock:
            self._keep_warm = True
            self._ensure_capture_task()

    async def stop_keep_warm(self) -> None:
        async with self._lock:
            self._keep_warm = False
            self._stop_capture_task_if_idle()

    async def mjpeg_frames(self) -> AsyncGenerator[bytes, None]:
        async with self._lock:
            self._mjpeg_clients += 1
            self._ensure_capture_task()

        last_frame_at: float | None = None
        try:
            while True:
                self._frame_event.clear()
                frame = self._latest_frame
                frame_at = self._latest_frame_at
                if frame and frame_at != last_frame_at:
                    last_frame_at = frame_at
                    yield self._format_mjpeg_part(frame)
                    continue

                try:
                    await asyncio.wait_for(self._frame_event.wait(), timeout=4.0)
                except asyncio.TimeoutError:
                    if self._latest_frame:
                        yield self._format_mjpeg_part(self._latest_frame)
        finally:
            async with self._lock:
                self._mjpeg_clients = max(0, self._mjpeg_clients - 1)
                self._stop_capture_task_if_idle()

    def status(self) -> dict[str, object]:
        cache_hit_rate = 0.0
        total_requests = self._cache_hits + self._cache_misses
        if total_requests > 0:
            cache_hit_rate = (self._cache_hits / total_requests) * 100
        
        return {
            "clients": len(self._clients) + self._mjpeg_clients,
            "websocket_clients": len(self._clients),
            "mjpeg_clients": self._mjpeg_clients,
            "running": bool(self._capture_task and not self._capture_task.done()),
            "keep_warm": self._keep_warm,
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
            "profile": self._settings.camera_stream_profile,
            "jpeg_quality": max(2, min(self._settings.camera_stream_jpeg_quality, 12)),
            "stream_width": max(0, self._settings.camera_stream_width),
            # 优化监控指标
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": round(cache_hit_rate, 2),
            "cache_size": len(self._frame_cache),
        }

    def latest_frame(self) -> bytes | None:
        return self._latest_frame

    def _decorate_frame(self, frame: bytes) -> bytes:
        return frame

    def _ensure_capture_task(self) -> None:
        if self._capture_task is None or self._capture_task.done():
            self._capture_task = asyncio.create_task(self._capture_loop())

    def _stop_capture_task_if_idle(self) -> None:
        if self._keep_warm or self._clients or self._mjpeg_clients > 0 or not self._capture_task or self._capture_task.done():
            return
        self._capture_task.cancel()
        self._capture_task = None

    def _has_consumers(self) -> bool:
        return bool(self._keep_warm or self._clients or self._mjpeg_clients > 0)

    async def _capture_loop(self) -> None:
        service = CameraService(self._settings)

        try:
            while True:
                async with self._lock:
                    if not self._has_consumers():
                        return

                preferred_mode = service.resolved_source_mode()
                try:
                    if preferred_mode == "local":
                        await self._run_local_snapshot_stream(service)
                    else:
                        await self._run_ffmpeg_stream(service)
                except Exception as exc:
                    self._last_error = f"{exc.__class__.__name__}: {exc}"
                    logger.warning("Camera stream failed, retrying: %s", self._last_error)
                    if preferred_mode != "local":
                        try:
                            await self._run_snapshot_stream(service)
                        except Exception as snapshot_exc:
                            self._last_error = f"{snapshot_exc.__class__.__name__}: {snapshot_exc}"
                            logger.warning("RTSP snapshot fallback failed, retrying: %s", self._last_error)
                            if service.can_use_local_camera_fallback() and not service.should_fail_closed_on_rtsp_errors():
                                try:
                                    await self._run_local_snapshot_stream(service)
                                except Exception as fallback_exc:
                                    self._last_error = f"{fallback_exc.__class__.__name__}: {fallback_exc}"
                                    logger.warning("Local camera fallback failed, retrying: %s", self._last_error)
                                    await self._run_snapshot_stream(service)
                            else:
                                await self._run_snapshot_stream(service)
                    else:
                        await self._run_snapshot_stream(service)
                    await asyncio.sleep(0.6)
        except asyncio.CancelledError:
            raise

    async def _run_ffmpeg_stream(self, service: CameraService) -> None:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        fps = max(1.0, min(self._settings.camera_stream_fps, 30.0))
        jpeg_quality = max(2, min(self._settings.camera_stream_jpeg_quality, 12))
        stream_width = max(0, self._settings.camera_stream_width)
        filters = [f"fps={fps:.2f}"]
        if stream_width > 0:
            filters.append(f"scale={stream_width}:-2:flags=bicubic")
        last_error = ""

        for url in service.stream_rtsp_urls:
            async with self._lock:
                if not self._has_consumers():
                    return

            transport = "udp" if "/udp/" in url.lower() else "tcp"
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-fflags",
                "discardcorrupt",
                "-probesize",
                "5000000",
                "-analyzeduration",
                "1000000",
                "-rtsp_transport",
                transport,
                "-timeout",
                str(int(self._settings.camera_snapshot_timeout_seconds * 1_000_000)),
                "-i",
                url,
                "-an",
                "-vf",
                ",".join(filters),
                "-q:v",
                str(jpeg_quality),
                "-flush_packets",
                "1",
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
                        if not self._has_consumers():
                            return

                    try:
                        chunk = await asyncio.wait_for(process.stdout.read(65536), timeout=4.0)
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
                        frame = self._decorate_frame(frame)
                        frame_count += 1
                        last_frame_at = time.monotonic()
                        self._latest_frame = frame
                        self._latest_frame_at = time.time()
                        self._latest_frame_size = len(frame)
                        self._last_error = None
                        self._frame_event.set()
                        self._record_frame()
                        await self._broadcast_frame(frame)
            finally:
                with suppress(ProcessLookupError):
                    process.kill()
                with suppress(ProcessLookupError, asyncio.TimeoutError):
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
        frame = self._decorate_frame(frame)
        self._latest_frame = frame
        self._latest_frame_at = time.time()
        self._latest_frame_size = len(frame)
        self._frame_event.set()
        self._record_frame()
        await self._broadcast_frame(frame)

    async def _run_snapshot_stream(self, service: CameraService) -> None:
        fps = max(1.0, min(self._settings.camera_stream_fps, 6.0))
        delay = 1.0 / fps
        delivered = 0
        self._active_url = "rtsp-snapshot-fallback"
        while delivered < max(3, int(fps * 4)):
            async with self._lock:
                if not self._has_consumers():
                    return
            
            # 优化2: 检查帧缓存
            cache_key = f"snapshot_{int(time.time() * fps)}"
            cached_frame = self._get_cached_frame(cache_key)
            
            if cached_frame is not None:
                frame = cached_frame
                self._cache_hits += 1
            else:
                try:
                    # 优化4: 使用asyncio.to_thread避免阻塞
                    frame, _headers = await asyncio.to_thread(service.capture_jpeg)
                    # 缓存帧
                    self._cache_frame(cache_key, frame)
                    self._cache_misses += 1
                except Exception:
                    return
            
            frame = self._decorate_frame(frame)
            self._latest_frame = frame
            self._latest_frame_at = time.time()
            self._latest_frame_size = len(frame)
            self._last_error = None
            self._frame_event.set()
            self._record_frame()
            await self._broadcast_frame(frame)
            delivered += 1
            await asyncio.sleep(delay)

    async def _run_local_snapshot_stream(self, service: CameraService) -> None:
        fps = max(1.0, min(self._settings.camera_stream_fps, 8.0))
        delay = 1.0 / fps
        await self._run_local_video_capture_stream(service, fps=fps, delay=delay)
        return
        self._active_url = service.local_source_label()
        while True:
            async with self._lock:
                if not self._has_consumers():
                    return
            
            # 优化2: 检查帧缓存
            cache_key = f"local_{int(time.time() * fps)}"
            cached_frame = self._get_cached_frame(cache_key)
            
            if cached_frame is not None:
                frame = cached_frame
                self._cache_hits += 1
            else:
                # 优化4: 使用asyncio.to_thread避免阻塞
                frame, _headers = await asyncio.to_thread(service.capture_local_jpeg)
                # 缓存帧
                self._cache_frame(cache_key, frame)
                self._cache_misses += 1
            
            frame = self._decorate_frame(frame)
            self._latest_frame = frame
            self._latest_frame_at = time.time()
            self._latest_frame_size = len(frame)
            self._last_error = None
            self._frame_event.set()
            self._record_frame()
            await self._broadcast_frame(frame)
            await asyncio.sleep(delay)

    async def _run_local_video_capture_stream(
        self,
        service: CameraService,
        *,
        fps: float,
        delay: float,
    ) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OPENCV_NOT_INSTALLED") from exc

        last_error = ""
        for backend_name, backend in service._local_camera_backends(cv2):  # noqa: SLF001
            try:
                cap = await asyncio.to_thread(
                    cv2.VideoCapture,
                    self._settings.camera_local_index,
                    backend,
                )
            except Exception as exc:
                last_error = f"{backend_name}: {exc.__class__.__name__}: {exc}"
                continue
            try:
                opened = await asyncio.to_thread(cap.isOpened)
                if not opened:
                    last_error = f"{backend_name}: Camera not opened"
                    continue
                with suppress(Exception):
                    await asyncio.to_thread(cap.set, cv2.CAP_PROP_BUFFERSIZE, 1)
                with suppress(Exception):
                    await asyncio.to_thread(cap.set, cv2.CAP_PROP_FRAME_WIDTH, 640)
                with suppress(Exception):
                    await asyncio.to_thread(cap.set, cv2.CAP_PROP_FRAME_HEIGHT, 480)
                with suppress(Exception):
                    await asyncio.to_thread(cap.set, cv2.CAP_PROP_FPS, max(4.0, min(fps, 8.0)))

                while True:
                    async with self._lock:
                        if not self._has_consumers():
                            return

                    ok, frame_data = await asyncio.to_thread(cap.read)
                    if not ok or frame_data is None:
                        raise RuntimeError("LOCAL_CAMERA_FRAME_READ_FAILED")
                    if not service.is_usable_local_frame(frame_data):
                        await asyncio.sleep(min(delay, 0.08))
                        continue

                    frame, _headers = await asyncio.to_thread(
                        service._encode_frame_to_jpeg,  # noqa: SLF001
                        frame_data,
                    )
                    frame = self._decorate_frame(frame)
                    self._latest_frame = frame
                    self._latest_frame_at = time.time()
                    self._latest_frame_size = len(frame)
                    self._last_error = None
                    self._frame_event.set()
                    self._record_frame()
                    await self._broadcast_frame(frame)
                    await asyncio.sleep(delay)
            except Exception as exc:
                last_error = f"{backend_name}: {exc.__class__.__name__}: {exc}"
            finally:
                with suppress(Exception):
                    await asyncio.to_thread(cap.release)

        raise RuntimeError(
            f"LOCAL_CAMERA_STREAM_FAILED: {last_error or 'no backend opened'}"
        )

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

        target_fps = max(1.0, min(self._settings.camera_stream_fps, 30.0))
        min_interval = 1.0 / target_fps
        now = time.monotonic()
        if now - self._last_broadcasted_at < min_interval:
            return

        async def send(websocket: WebSocket) -> tuple[WebSocket, bool]:
            try:
                await asyncio.wait_for(
                    self._send_frame(websocket, frame),
                    timeout=max(0.05, self._settings.camera_stream_send_timeout_seconds),
                )
                return websocket, True
            except (asyncio.TimeoutError, Exception):
                return websocket, False

        results = await asyncio.gather(*(send(websocket) for websocket in clients), return_exceptions=False)
        stale = [websocket for websocket, ok in results if not ok]
        sent = sum(1 for _websocket, ok in results if ok)
        if sent > 0:
            self._last_broadcasted_at = now

        self._record_broadcast(sent)

        if stale:
            async with self._lock:
                for websocket in stale:
                    self._clients.discard(websocket)

    @staticmethod
    def _format_mjpeg_part(image: bytes) -> bytes:
        return (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(image)}\r\n\r\n".encode("ascii")
            + image
            + b"\r\n"
        )

    @staticmethod
    async def _send_frame(websocket: WebSocket, frame: bytes) -> None:
        await websocket.send_bytes(frame)

    def _mask_url(self, url: str | None) -> str | None:
        if not url:
            return None
        password = self._settings.camera_password
        return url.replace(password, "***") if password else url

    def _get_cached_frame(self, cache_key: str) -> bytes | None:
        """获取缓存的帧，如果过期则返回None"""
        if cache_key not in self._frame_cache:
            return None
        
        frame, timestamp = self._frame_cache[cache_key]
        if time.time() - timestamp > self._frame_cache_ttl:
            # 缓存过期，删除
            del self._frame_cache[cache_key]
            return None
        
        return frame

    def _cache_frame(self, cache_key: str, frame: bytes) -> None:
        """缓存帧，并清理过期缓存"""
        self._frame_cache[cache_key] = (frame, time.time())
        
        # 清理过期缓存（保持缓存大小合理）
        if len(self._frame_cache) > 10:
            current_time = time.time()
            expired_keys = [
                key for key, (_, timestamp) in self._frame_cache.items()
                if current_time - timestamp > self._frame_cache_ttl
            ]
            for key in expired_keys:
                del self._frame_cache[key]


class CameraDetectionFrameHub(CameraFrameHub):
    """Camera hub that paints the latest fall-detection bbox onto frames."""

    def __init__(
        self,
        settings: Settings,
        *,
        event_provider: Callable[[], dict[str, Any] | None],
        max_event_age_seconds: float = 8.0,
    ) -> None:
        super().__init__(settings)
        self._event_provider = event_provider
        self._max_event_age_seconds = max_event_age_seconds

    def _decorate_frame(self, frame: bytes) -> bytes:
        event = self._event_provider()
        if not isinstance(event, dict):
            return frame

        bbox = event.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return frame

        frame_width = self._coerce_positive(event.get("frame_width"))
        frame_height = self._coerce_positive(event.get("frame_height"))
        if frame_width <= 0 or frame_height <= 0:
            return frame

        event_timestamp = self._coerce_positive(event.get("_observed_at"))
        if event_timestamp > 0 and time.time() - event_timestamp > self._max_event_age_seconds:
            return frame

        try:
            coords = [float(value) for value in bbox]
        except (TypeError, ValueError):
            return frame

        try:
            import cv2
            import numpy as np
        except Exception:
            return frame

        image = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return frame

        height, width = image.shape[:2]
        x1, y1, x2, y2 = coords
        x1 = max(0, min(width - 1, int(round((x1 / frame_width) * width))))
        x2 = max(0, min(width - 1, int(round((x2 / frame_width) * width))))
        y1 = max(0, min(height - 1, int(round((y1 / frame_height) * height))))
        y2 = max(0, min(height - 1, int(round((y2 / frame_height) * height))))
        if x2 <= x1 or y2 <= y1:
            return frame

        state = str(event.get("state") or event.get("event_type") or "tracked").strip() or "tracked"
        fall_score = self._coerce_positive(event.get("fall_score"))
        posture_label = str(event.get("posture_label") or "").strip()
        label = f"{state} {fall_score:.2f}".strip()
        if posture_label:
            label = f"{label} {posture_label}".strip()

        alert_like = state in {
            "suspected_fall",
            "confirmed_fall",
            "post_fall_monitoring",
            "injury_watch",
            "abnormal_recovery",
            "needs_assistance",
            "emergency",
        }
        color = (38, 78, 255) if not alert_like else (32, 90, 235)
        if alert_like:
            color = (0, 80, 255)

        thickness = 3 if alert_like else 2
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)

        text_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.62, 2)
        text_w, text_h = text_size
        text_x = x1
        text_y = max(text_h + 10, y1 - 8)
        cv2.rectangle(
            image,
            (text_x - 4, text_y - text_h - 8),
            (text_x + text_w + 6, text_y + baseline + 4),
            color,
            -1,
        )
        cv2.putText(
            image,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        return encoded.tobytes() if ok else frame

    @staticmethod
    def _coerce_positive(value: object) -> float:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0


class CameraPoseFrameHub(CameraFrameHub):
    """Camera hub that paints the latest pose tracks onto frames."""

    _COCO_BONES = (
        (5, 6),
        (5, 7),
        (7, 9),
        (6, 8),
        (8, 10),
        (5, 11),
        (6, 12),
        (11, 12),
        (11, 13),
        (13, 15),
        (12, 14),
        (14, 16),
        (0, 5),
        (0, 6),
    )

    def __init__(
        self,
        settings: Settings,
        *,
        payload_provider: Callable[[], dict[str, Any] | None],
        max_payload_age_seconds: float = 5.0,
    ) -> None:
        super().__init__(settings)
        self._payload_provider = payload_provider
        self._max_payload_age_seconds = max_payload_age_seconds

    def _decorate_frame(self, frame: bytes) -> bytes:
        payload = self._payload_provider()
        if not isinstance(payload, dict):
            return frame

        tracks = payload.get("tracks")
        if not isinstance(tracks, list) or not tracks:
            return frame

        frame_width = self._coerce_positive(payload.get("frame_width"))
        frame_height = self._coerce_positive(payload.get("frame_height"))
        if frame_width <= 0 or frame_height <= 0:
            return frame

        observed_at = self._coerce_positive(payload.get("_observed_at"))
        if observed_at > 0 and time.time() - observed_at > self._max_payload_age_seconds:
            return frame

        try:
            import cv2
            import numpy as np
        except Exception:
            return frame

        image = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return frame

        height, width = image.shape[:2]
        for item in tracks:
            if not isinstance(item, dict):
                continue
            bbox = item.get("bbox")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                continue
            try:
                x1, y1, x2, y2 = [float(value) for value in bbox]
            except (TypeError, ValueError):
                continue
            x1 = max(0, min(width - 1, int(round((x1 / frame_width) * width))))
            x2 = max(0, min(width - 1, int(round((x2 / frame_width) * width))))
            y1 = max(0, min(height - 1, int(round((y1 / frame_height) * height))))
            y2 = max(0, min(height - 1, int(round((y2 / frame_height) * height))))
            if x2 <= x1 or y2 <= y1:
                continue

            label = str(item.get("posture_label") or "unknown").strip() or "unknown"
            score = self._coerce_positive(item.get("posture_score"))
            track_id = str(item.get("track_id") or "?")
            risk_like = label in {
                "lying_floor",
                "floor_risk",
                "fall_like",
                "suspected_fall",
                "confirmed_fall",
            }
            color = (0, 0, 255) if risk_like else (0, 80, 255)

            cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
            text = f"id={track_id} {label} {score:.2f}"
            text_size, baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 2)
            text_w, text_h = text_size
            text_x = x1
            text_y = max(text_h + 10, y1 - 8)
            cv2.rectangle(
                image,
                (text_x - 4, text_y - text_h - 8),
                (text_x + text_w + 6, text_y + baseline + 4),
                color,
                -1,
            )
            cv2.putText(
                image,
                text,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            keypoints = item.get("keypoints")
            if isinstance(keypoints, list):
                scaled_points: list[tuple[int, int, float] | None] = []
                for point in keypoints:
                    if not isinstance(point, (list, tuple)) or len(point) < 2:
                        scaled_points.append(None)
                        continue
                    try:
                        px = float(point[0])
                        py = float(point[1])
                        pconf = float(point[2]) if len(point) >= 3 else 1.0
                    except (TypeError, ValueError):
                        scaled_points.append(None)
                        continue
                    tx = max(0, min(width - 1, int(round((px / frame_width) * width))))
                    ty = max(0, min(height - 1, int(round((py / frame_height) * height))))
                    scaled_points.append((tx, ty, pconf))

                for bone_a, bone_b in self._COCO_BONES:
                    if bone_a >= len(scaled_points) or bone_b >= len(scaled_points):
                        continue
                    point_a = scaled_points[bone_a]
                    point_b = scaled_points[bone_b]
                    if point_a is None or point_b is None:
                        continue
                    if point_a[2] < 0.18 or point_b[2] < 0.18:
                        continue
                    cv2.line(
                        image,
                        (point_a[0], point_a[1]),
                        (point_b[0], point_b[1]),
                        color,
                        3,
                        cv2.LINE_AA,
                    )

                for point in scaled_points:
                    if point is None or point[2] < 0.15:
                        continue
                    tx, ty, _confidence = point
                    cv2.circle(image, (tx, ty), 5, (255, 255, 255), -1)
                    cv2.circle(image, (tx, ty), 2, color, -1)

        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        return encoded.tobytes() if ok else frame

    @staticmethod
    def _coerce_positive(value: object) -> float:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0
