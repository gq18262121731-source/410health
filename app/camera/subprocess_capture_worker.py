from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from app.camera.capture_process_protocol import CaptureProtocolError, read_frame_packet
from app.camera.capture_watchdog import drain_stderr, is_process_alive, terminate_process
from app.camera.capture_worker import CaptureWorkerStatus
from app.camera.frame_buffer import FrameBuffer
from app.camera.source_models import CameraSourceConfig
from app.core.config import Settings
from app.core.logger import get_logger
from app.monitoring.metrics import FPSMeter, LatencyMeter

logger = get_logger(__name__)


@dataclass
class SubprocessCaptureStatus:
    capture_backend: str = "subprocess_opencv"
    capture_process_alive: bool = False
    capture_process_pid: int | None = None
    capture_process_restart_count: int = 0
    capture_process_last_frame_age_ms: float | None = None
    capture_process_last_error: str | None = None
    capture_process_last_exit_code: int | None = None
    capture_process_last_log: str | None = None
    capture_process_last_failure_reason: str | None = None
    capture_process_open_started_at: str | None = None
    capture_process_opened_at: str | None = None
    capture_process_first_frame_at: str | None = None
    capture_process_source_fps: float | None = None
    capture_ipc_decode_errors: int = 0
    capture_ipc_dropped_frames: int = 0
    capture_output_width: int | None = None
    capture_output_height: int | None = None


class SubprocessCaptureWorker:
    def __init__(
        self,
        config: CameraSourceConfig,
        frame_buffer: FrameBuffer,
        settings: Settings,
    ) -> None:
        self.config = config
        self.frame_buffer = frame_buffer
        self.settings = settings
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._status = CaptureWorkerStatus()
        self._process_status = SubprocessCaptureStatus()
        self._fps = FPSMeter()
        self._read_latency = LatencyMeter()
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._last_packet_monotonic: float | None = None
        self._last_packet_seq: int | None = None
        self._child_started_monotonic: float | None = None
        self._manual_stop = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._manual_stop = False
        self._thread = threading.Thread(
            target=self._supervisor_loop,
            name=f"capture-subprocess-{self.config.camera_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._manual_stop = True
        self._stop_event.set()
        self._terminate_child("manual_stop")
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        with self._lock:
            self._status.running = False
            self._status.connected = False
            self._status.stream_state = "disconnected"

    def status(self) -> CaptureWorkerStatus:
        packet = self.frame_buffer.latest()
        with self._lock:
            status = CaptureWorkerStatus(**self._status.__dict__)
            process_status = SubprocessCaptureStatus(**self._process_status.__dict__)
        if packet:
            status.frame_seq = packet.seq
            status.frame_width = packet.width
            status.frame_height = packet.height
            status.frame_age_ms = packet.age_ms
            status.last_frame_at = packet.captured_at_iso
        status.stream_state = self._derive_stream_state(status, process_status)
        status.capture_fps = self._fps.fps
        status.read_latency_avg_ms = self._read_latency.avg_ms
        for key, value in process_status.__dict__.items():
            setattr(status, key, value)
        return status

    def _supervisor_loop(self) -> None:
        with self._lock:
            self._status.running = True
            self._status.stream_state = "connecting"
            self._status.last_error = None

        while not self._stop_event.is_set():
            self._start_child()
            while not self._stop_event.is_set():
                proc = self._proc
                if proc is None:
                    break
                exit_code = proc.poll()
                if exit_code is not None:
                    self._record_child_exit(exit_code)
                    break
                if self._is_child_frame_timeout():
                    self._terminate_child("capture_process_frame_timeout")
                    break
                self._stop_event.wait(0.25)
            if self._stop_event.is_set():
                break
            self._restart_sleep()

    def _start_child(self) -> None:
        self._cleanup_existing_child_before_start()
        self._last_packet_monotonic = None
        self._last_packet_seq = None
        self._child_started_monotonic = time.monotonic()
        with self._lock:
            self._status.stream_state = "connecting"
            self._status.connected = False
            self._status.reconnect_reason = None
            self._process_status.capture_process_last_error = None
            self._process_status.capture_process_last_exit_code = None
            self._process_status.capture_process_last_frame_age_ms = None

        cmd = [
            sys.executable,
            "-m",
            "app.camera.capture_process",
            "--rtsp-url",
            self.config.source_url,
            "--output-height",
            str(self.config.output_height or self.settings.capture_process_output_height),
            "--jpeg-quality",
            str(self.config.jpeg_quality or self.settings.capture_jpeg_quality),
            "--write-fps",
            str(self.config.write_fps or self.settings.capture_process_write_fps),
            "--buffersize",
            str(self.settings.opencv_capture_buffersize),
        ]
        proc = subprocess.Popen(
            cmd,
            cwd=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            bufsize=0,
            text=False,
        )
        self._proc = proc
        with self._lock:
            self._process_status.capture_process_pid = proc.pid
            self._process_status.capture_process_alive = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(proc,),
            name=f"capture-subprocess-reader-{self.config.camera_id}",
            daemon=True,
        )
        self._reader_thread.start()
        self._stderr_thread = threading.Thread(
            target=drain_stderr,
            args=(proc.stderr, self._record_child_stderr),
            name=f"capture-subprocess-stderr-{self.config.camera_id}",
            daemon=True,
        )
        self._stderr_thread.start()
        logger.info(
            "capture_process_started camera_id=%s pid=%s",
            self.config.camera_id,
            proc.pid,
        )

    def _reader_loop(self, proc: subprocess.Popen) -> None:
        if proc.stdout is None:
            self._set_error("capture process stdout missing")
            return
        try:
            import cv2

            while not self._stop_event.is_set() and is_process_alive(proc):
                read_started = time.monotonic()
                with self._lock:
                    self._status.last_read_started_at = datetime.now(timezone.utc).isoformat()
                packet = read_frame_packet(proc.stdout)
                read_latency_ms = (time.monotonic() - read_started) * 1000
                image = cv2.imdecode(np.frombuffer(packet.payload, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise CaptureProtocolError("failed to decode capture packet jpeg")
                self._last_packet_monotonic = time.monotonic()
                if self._last_packet_seq is not None and packet.seq > self._last_packet_seq + 1:
                    with self._lock:
                        self._process_status.capture_ipc_dropped_frames += packet.seq - self._last_packet_seq - 1
                self._last_packet_seq = packet.seq
                frame_packet = self.frame_buffer.update(image)
                self._fps.tick()
                with self._lock:
                    self._status.connected = True
                    self._status.stream_state = "connected"
                    self._status.frame_seq = frame_packet.seq
                    self._status.frame_width = frame_packet.width
                    self._status.frame_height = frame_packet.height
                    self._status.frame_age_ms = frame_packet.age_ms
                    self._status.last_frame_at = frame_packet.captured_at_iso
                    self._status.read_latency_ms = round(read_latency_ms, 2)
                    self._read_latency.add(read_latency_ms)
                    self._status.read_latency_avg_ms = self._read_latency.avg_ms
                    self._status.read_latency_max_ms = round(
                        max(read_latency_ms, self._status.read_latency_max_ms or 0),
                        2,
                    )
                    self._status.last_read_completed_at = datetime.now(timezone.utc).isoformat()
                    self._status.consecutive_slow_reads = 0
                    self._status.last_error = None
                    self._process_status.capture_output_width = packet.width
                    self._process_status.capture_output_height = packet.height
        except EOFError:
            if self._manual_stop or self._stop_event.is_set():
                return
            self._set_error("capture process stream closed", overwrite_process_error=False)
        except Exception as exc:
            with self._lock:
                self._process_status.capture_ipc_decode_errors += 1
            self._set_error(f"capture ipc reader failed: {exc}")

    def _record_child_stderr(self, line: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._process_status.capture_process_last_log = line
            if line.startswith("capture_process_open_start"):
                self._process_status.capture_process_open_started_at = now
            elif line.startswith("capture_process_open_ok"):
                self._process_status.capture_process_opened_at = now
                self._process_status.capture_process_last_failure_reason = None
                source_fps = _extract_float_token(line, "source_fps")
                if source_fps is not None:
                    self._process_status.capture_process_source_fps = source_fps
            elif line.startswith("capture_process_first_frame_ok"):
                self._process_status.capture_process_first_frame_at = now
                self._process_status.capture_process_last_failure_reason = None
            elif line.startswith("capture_process_open_failed"):
                self._process_status.capture_process_last_failure_reason = "open_failed"
            elif line.startswith("capture_process_read_failed"):
                self._process_status.capture_process_last_failure_reason = "read_failed"
            elif line.startswith("capture_process_encode_failed"):
                self._process_status.capture_process_last_failure_reason = "encode_failed"
            self._process_status.capture_process_last_error = line
        logger.warning(
            "capture_process_stderr camera_id=%s line=%s",
            self.config.camera_id,
            line,
        )

    def _record_child_exit(self, exit_code: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._status.connected = False
            self._status.stream_state = "reconnecting"
            self._status.reconnect_count += 1
            self._status.reconnect_reason = self._status.reconnect_reason or "capture_process_exit"
            self._status.last_restart_at = now
            self._status.last_restart_reason = self._status.reconnect_reason
            self._process_status.capture_process_alive = False
            self._process_status.capture_process_last_exit_code = exit_code
            if exit_code not in (0, None):
                self._process_status.capture_process_last_failure_reason = "capture_process_exit"
            self._process_status.capture_process_restart_count += 1
        if self._proc and self._proc.poll() is not None:
            self._proc = None
        logger.warning(
            "capture_process_exited camera_id=%s exit_code=%s",
            self.config.camera_id,
            exit_code,
        )

    def _terminate_child(self, reason: str) -> None:
        proc = self._proc
        if proc is None:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._status.reconnect_reason = reason
            self._status.connected = False
            self._status.stream_state = "reconnecting"
        exit_code = terminate_process(proc)
        with self._lock:
            self._process_status.capture_process_alive = False
            self._process_status.capture_process_last_exit_code = exit_code
            if not self._manual_stop:
                self._status.reconnect_count += 1
                self._status.last_restart_at = now
                self._status.last_restart_reason = reason
                self._process_status.capture_process_restart_count += 1
        logger.warning(
            "capture_process_terminated camera_id=%s reason=%s exit_code=%s",
            self.config.camera_id,
            reason,
            exit_code,
        )
        self._proc = None
        self._child_started_monotonic = None

    def _cleanup_existing_child_before_start(self) -> None:
        proc = self._proc
        if proc is None:
            return
        if proc.poll() is not None:
            self._proc = None
            return
        exit_code = terminate_process(proc)
        with self._lock:
            self._process_status.capture_process_alive = False
            self._process_status.capture_process_last_exit_code = exit_code
            self._status.reconnect_reason = "replace_existing_capture_process"
        logger.warning(
            "capture_process_replaced camera_id=%s old_pid=%s exit_code=%s",
            self.config.camera_id,
            proc.pid,
            exit_code,
        )
        self._proc = None
        self._child_started_monotonic = None

    def _is_child_frame_timeout(self) -> bool:
        if self._last_packet_monotonic is None:
            proc = self._proc
            if proc is None:
                return False
            if self._child_started_monotonic is None:
                return False
            open_age_ms = (time.monotonic() - self._child_started_monotonic) * 1000
            with self._lock:
                self._process_status.capture_process_last_frame_age_ms = round(open_age_ms, 2)
                if open_age_ms > self.settings.capture_process_frame_timeout_ms:
                    self._process_status.capture_process_last_failure_reason = "open_timeout"
            return open_age_ms > self.settings.capture_process_frame_timeout_ms
        age_ms = (time.monotonic() - self._last_packet_monotonic) * 1000
        with self._lock:
            self._process_status.capture_process_last_frame_age_ms = round(age_ms, 2)
        return age_ms > self.settings.capture_process_frame_timeout_ms

    def _restart_sleep(self) -> None:
        if self.settings.capture_process_max_restarts > 0:
            with self._lock:
                restart_count = self._process_status.capture_process_restart_count
            if restart_count > self.settings.capture_process_max_restarts:
                self._set_error("capture process max restarts exceeded")
                self._stop_event.set()
                return
        self._stop_event.wait(max(0, self.settings.capture_process_restart_ms) / 1000)

    def _set_error(self, message: str, *, overwrite_process_error: bool = True) -> None:
        with self._lock:
            self._status.last_error = message
            self._process_status.capture_process_last_failure_reason = message
            if overwrite_process_error or not self._process_status.capture_process_last_error:
                self._process_status.capture_process_last_error = message
        logger.error("capture_subprocess_error camera_id=%s error=%s", self.config.camera_id, message)

    def _derive_stream_state(
        self,
        status: CaptureWorkerStatus,
        process_status: SubprocessCaptureStatus,
    ) -> str:
        if not status.running:
            return "disconnected"
        if status.stream_state in {"connecting", "reconnecting"}:
            return status.stream_state
        if not process_status.capture_process_alive:
            return "reconnecting"
        if status.frame_age_ms is None:
            return "connecting"
        if status.frame_age_ms > self.settings.stream_stale_threshold_ms:
            return "stale"
        return "connected"


def _extract_float_token(line: str, name: str) -> float | None:
    prefix = f"{name}="
    for part in line.split():
        if not part.startswith(prefix):
            continue
        try:
            return float(part[len(prefix):])
        except ValueError:
            return None
    return None
