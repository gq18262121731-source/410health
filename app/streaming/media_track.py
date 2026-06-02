from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import numpy as np

from app.camera.capture_worker import CaptureWorkerStatus
from app.camera.frame_buffer import FrameBuffer
from app.core.config import Settings


class LatestFrameVideoTrack:
    def __init__(
        self,
        frame_buffer: FrameBuffer,
        settings: Settings,
        *,
        status_provider: Callable[[], CaptureWorkerStatus | None] | None = None,
    ) -> None:
        from aiortc import VideoStreamTrack

        class _Track(VideoStreamTrack):
            def __init__(self) -> None:
                super().__init__()
                self._buffer = frame_buffer
                self._settings = settings
                self._status_provider = status_provider
                self._last_seq = 0
                self._fallback_frames: dict[tuple[int, int], np.ndarray] = {}

            async def recv(self):
                from av import VideoFrame

                pts, time_base = await self.next_timestamp()
                expected_interval = 1 / max(self._settings.webrtc_video_fps, 1)
                packet = self._buffer.wait_for_next(self._last_seq, timeout_sec=expected_interval)
                if self._can_send_camera_frame(packet):
                    frame = packet.frame
                    self._last_seq = packet.seq
                else:
                    await asyncio.sleep(0.02)
                    frame = self._offline_frame_for(packet)
                video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
                video_frame.pts = pts
                video_frame.time_base = time_base
                return video_frame

            def _can_send_camera_frame(self, packet) -> bool:
                if packet is None:
                    return False
                if packet.age_ms > self._settings.stream_stale_threshold_ms:
                    return False

                status = self._status_provider() if self._status_provider else None
                if status is None:
                    return True
                if not status.running or not status.connected:
                    return False
                if status.stream_state != "connected":
                    return False
                if (
                    status.frame_age_ms is not None
                    and status.frame_age_ms > self._settings.stream_stale_threshold_ms
                ):
                    return False
                return True

            def _offline_frame_for(self, packet) -> np.ndarray:
                width = packet.width if packet is not None else self._settings.mock_camera_width
                height = packet.height if packet is not None else self._settings.mock_camera_height
                width = max(160, int(width or self._settings.mock_camera_width))
                height = max(90, int(height or self._settings.mock_camera_height))
                key = (width, height)
                cached = self._fallback_frames.get(key)
                if cached is not None:
                    return cached

                frame = np.zeros((height, width, 3), dtype=np.uint8)
                frame[:, :] = (18, 24, 28)
                border = max(4, min(width, height) // 80)
                amber = (42, 168, 255)
                frame[:border, :] = amber
                frame[-border:, :] = amber
                frame[:, :border] = amber
                frame[:, -border:] = amber

                stripe_width = max(12, min(width, height) // 24)
                for offset in range(-height, width, stripe_width * 3):
                    x0 = max(0, offset)
                    x1 = min(width, offset + stripe_width)
                    if x1 > x0:
                        frame[:, x0:x1] = (32, 45, 52)

                self._fallback_frames[key] = frame
                return frame

        self.track = _Track()
