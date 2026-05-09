from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from itertools import product

import cv2

from .config import CameraConfig


logger = logging.getLogger(__name__)


@dataclass
class FrameSnapshot:
    latest_jpeg: bytes | None
    latest_frame_at: float | None
    frame_count: int
    last_error: str | None
    last_error_at: float | None
    last_opened_at: float | None
    running: bool
    reconnect_count: int
    consecutive_failures: int
    current_stream: str


class FrameStore:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.latest_jpeg: bytes | None = None
        self.latest_frame_at: float | None = None
        self.frame_count = 0
        self.last_error: str | None = None
        self.last_error_at: float | None = None
        self._last_logged_error_at: float | None = None
        self.running = False
        self.last_opened_at: float | None = None
        self.current_stream = "unknown"
        self.reconnect_count = 0
        self.consecutive_failures = 0

    def update(self, jpeg: bytes) -> None:
        with self.lock:
            self.latest_jpeg = jpeg
            self.latest_frame_at = time.time()
            self.frame_count += 1
            self.last_error = None
            self.last_error_at = None
            self.consecutive_failures = 0

    def set_error(self, message: str) -> None:
        now = time.time()
        should_log = False
        with self.lock:
            self.last_error = message
            self.last_error_at = now
            self.consecutive_failures += 1
            if self._last_logged_error_at is None or now - self._last_logged_error_at >= 2.0:
                should_log = True
                self._last_logged_error_at = now
        if should_log:
            logger.warning(message)

    def mark_opened(self, stream: str) -> None:
        with self.lock:
            self.last_opened_at = time.time()
            self.current_stream = stream
            self.reconnect_count += 1

    def snapshot(self) -> FrameSnapshot:
        with self.lock:
            return FrameSnapshot(
                latest_jpeg=self.latest_jpeg,
                latest_frame_at=self.latest_frame_at,
                frame_count=self.frame_count,
                last_error=self.last_error,
                last_error_at=self.last_error_at,
                last_opened_at=self.last_opened_at,
                running=self.running,
                reconnect_count=self.reconnect_count,
                consecutive_failures=self.consecutive_failures,
                current_stream=self.current_stream,
            )


class CameraRuntime:
    def __init__(
        self,
        camera_config: CameraConfig,
        jpeg_quality: int,
        frame_interval_seconds: float,
        viewer_auth_enabled: bool = False,
        viewer_auth_username: str = "camera",
        viewer_auth_password: str = "camera",
    ) -> None:
        self.camera_config = camera_config
        self.jpeg_quality = max(40, min(jpeg_quality, 95))
        self.frame_interval_seconds = max(0.02, frame_interval_seconds)
        self.viewer_auth_enabled = viewer_auth_enabled
        self.viewer_auth_username = viewer_auth_username
        self.viewer_auth_password = viewer_auth_password
        self.frame_store = FrameStore()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._last_successful_stream: str | None = None
        self._read_retry_count = 20
        self._read_retry_sleep_seconds = 0.05
        self._max_read_failures_before_reconnect = 10
        self._max_stale_seconds_before_reconnect = max(3.0, self.frame_interval_seconds * 80)
        self._stream_failure_times: dict[str, list[float]] = {}
        self._stream_cooldown_until: dict[str, float] = {}
        self._stream_failure_window_seconds = 120.0
        self._stream_failure_threshold = 2
        self._stream_cooldown_seconds = 90.0

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._worker = threading.Thread(target=self._capture_loop, daemon=True, name="camera-runtime")
        self._worker.start()
        logger.info("Camera runtime started for %s", self.camera_config.masked_rtsp_url)

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        logger.info("Camera runtime stopped")

    def switch_stream(self, stream: str) -> None:
        self.camera_config.stream = stream
        self._last_successful_stream = stream
        self._stream_failure_times.clear()
        self._stream_cooldown_until.clear()
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        self._stop_event = threading.Event()
        self.start()
        logger.info("Switched stream to %s", stream)

    def stream_guard_status(self) -> dict[str, object]:
        now = time.time()
        cooldowns = {
            stream: round(until - now, 1)
            for stream, until in self._stream_cooldown_until.items()
            if until > now
        }
        return {
            "preferred_stream": self._last_successful_stream or self.camera_config.stream,
            "cooldowns": cooldowns,
            "failure_counts": {
                stream: len([item for item in failures if now - item <= self._stream_failure_window_seconds])
                for stream, failures in self._stream_failure_times.items()
            },
        }

    def _capture_loop(self) -> None:
        self.frame_store.running = True
        while not self._stop_event.is_set():
            self._capture_with_opencv_candidates()
            time.sleep(1.0)
        self.frame_store.running = False

    def _capture_with_opencv_candidates(self) -> None:
        logger.info("Using OpenCV capture path")
        candidates = self._build_rtsp_candidates()
        opened = None
        for stream, url in candidates:
            logger.info("Trying RTSP candidate: %s", self._mask_url(url))
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
            if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)

            if not cap.isOpened():
                cap.release()
                continue

            ok = False
            frame = None
            started = time.perf_counter()
            while time.perf_counter() - started < 4.0 and not self._stop_event.is_set():
                ok, frame = cap.read()
                if ok and frame is not None:
                    break
                time.sleep(0.05)
            if not ok or frame is None:
                cap.release()
                continue
            opened = (stream, url, cap, frame)
            break

        if opened is None:
            self.frame_store.set_error("Unable to open RTSP stream")
            time.sleep(2.0)
            return

        stream, url, cap, first_frame = opened
        self._last_successful_stream = stream
        self.frame_store.mark_opened(stream)
        logger.info("Opened RTSP stream via OpenCV: %s", self._mask_url(url))
        stream_failed = False
        try:
            self._publish_frame(first_frame)
            read_failures = 0
            last_good_read_at = time.perf_counter()
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    recovered = False
                    for _ in range(self._read_retry_count):
                        time.sleep(self._read_retry_sleep_seconds)
                        ok, frame = cap.read()
                        if ok and frame is not None:
                            recovered = True
                            break
                    if not recovered:
                        read_failures += 1
                        stale_for = time.perf_counter() - last_good_read_at
                        if read_failures >= 3:
                            self.frame_store.set_error(
                                f"Failed to read frame ({read_failures} consecutive failures, stale for {stale_for:.1f}s)"
                            )
                        if (
                            read_failures >= self._max_read_failures_before_reconnect
                            or stale_for >= self._max_stale_seconds_before_reconnect
                        ):
                            stream_failed = True
                            break
                        continue
                read_failures = 0
                last_good_read_at = time.perf_counter()
                self._publish_frame(frame)
                time.sleep(self.frame_interval_seconds)
        finally:
            cap.release()
            if stream_failed and not self._stop_event.is_set():
                self._mark_stream_failure(stream)

    def _mark_stream_failure(self, stream: str) -> None:
        now = time.time()
        failures = self._stream_failure_times.setdefault(stream, [])
        failures.append(now)
        failures[:] = [item for item in failures if now - item <= self._stream_failure_window_seconds]
        if len(failures) >= self._stream_failure_threshold:
            self._stream_cooldown_until[stream] = now + self._stream_cooldown_seconds
            logger.warning(
                "Stream %s is unstable (%s failures in %.0fs); cooling it down for %.0fs",
                stream,
                len(failures),
                self._stream_failure_window_seconds,
                self._stream_cooldown_seconds,
            )

    def _publish_frame(self, frame) -> None:
        encoded_ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
        )
        if encoded_ok:
            self.frame_store.update(encoded.tobytes())

    def _build_rtsp_candidates(self) -> list[tuple[str, str]]:
        # Current field evidence suggests 554/tcp with admin/admin is valid on this device, while
        # historic docs may still mention 10554 or other passwords. We prioritize the currently
        # observed combinations and fall back conservatively.
        users = [self.camera_config.username, "admin"]
        passwords = [self.camera_config.password, "admin", "8888888", "123456"]
        ports = [self.camera_config.rtsp_port, 554, 10554]
        transports = [self.camera_config.transport, "tcp", "udp"]
        streams = [self._last_successful_stream or self.camera_config.stream, "av0_0", "av0_1"]

        seen: set[str] = set()
        candidates: list[tuple[str, str]] = []
        for user, password, port, transport, stream in product(users, passwords, ports, transports, streams):
            url = f"rtsp://{user}:{password}@{self.camera_config.host}:{port}/{transport}/{stream}"
            if url in seen:
                continue
            seen.add(url)
            candidates.append((stream, url))

        now = time.time()

        def priority(item: tuple[str, str]) -> tuple[int, int, int]:
            stream, url = item
            score = 0
            if stream == self._last_successful_stream:
                score -= 3
            if stream == self.camera_config.stream:
                score -= 2
            if self._stream_cooldown_until.get(stream, 0.0) > now:
                score += 60
            if ":554/" in url:
                score -= 8
            if "/tcp/" in url:
                score -= 4
            if "@{}:".format(self.camera_config.host) in url and "admin:admin@" in url:
                score -= 10
            if stream == "av0_0":
                score -= 2
            return (score, len(url), 0)

        candidates.sort(key=priority)
        return candidates

    def _mask_url(self, url: str) -> str:
        password = self.camera_config.password
        masked = url
        for secret in {password, "admin", "8888888", "123456"}:
            if secret:
                masked = masked.replace(secret, "***")
        return masked
