from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.camera.capture_worker import CaptureWorker, CaptureWorkerStatus
from app.camera.frame_buffer import FrameBuffer
from app.camera.source_models import CameraSourceConfig
from app.camera.subprocess_capture_worker import SubprocessCaptureWorker
from app.core.config import Settings


@dataclass
class CameraRuntime:
    config: CameraSourceConfig
    frame_buffer: FrameBuffer
    worker: CaptureWorker | SubprocessCaptureWorker
    main_frame_buffer: FrameBuffer | None = None
    analysis_frame_buffer: FrameBuffer | None = None
    main_worker: CaptureWorker | SubprocessCaptureWorker | None = None
    analysis_worker: CaptureWorker | SubprocessCaptureWorker | None = None
    main_config: CameraSourceConfig | None = None
    analysis_config: CameraSourceConfig | None = None
    dual_stream_enabled: bool = False
    display_source_current: str = "single"
    display_fallback_active: bool = False
    display_fallback_since_monotonic: float | None = None

    def __post_init__(self) -> None:
        if self.main_frame_buffer is None:
            self.main_frame_buffer = self.frame_buffer
        if self.analysis_frame_buffer is None:
            self.analysis_frame_buffer = self.frame_buffer
        if self.main_worker is None:
            self.main_worker = self.worker
        if self.analysis_worker is None:
            self.analysis_worker = self.worker
        if self.main_config is None:
            self.main_config = self.config
        if self.analysis_config is None:
            self.analysis_config = self.config


class CameraSourceManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._runtimes: dict[str, CameraRuntime] = {}
        self._lock = threading.Lock()

    def start_source(self, config: CameraSourceConfig) -> tuple[CameraRuntime, bool]:
        with self._lock:
            existing = self._runtimes.get(config.camera_id)
            if existing:
                if existing.config.source_url != config.source_url:
                    raise ValueError(
                        f"camera {config.camera_id} is already running with another source"
                    )
                return existing, False
            runtime = self._create_runtime(config)
            self._runtimes[config.camera_id] = runtime
            self._start_runtime(runtime)
            return runtime, True

    def stop_source(self, camera_id: str) -> bool:
        with self._lock:
            runtime = self._runtimes.pop(camera_id, None)
        if not runtime:
            return False
        self._stop_runtime(runtime)
        return True

    def get_runtime(self, camera_id: str) -> CameraRuntime | None:
        with self._lock:
            return self._runtimes.get(camera_id)

    def get_buffer(self, camera_id: str) -> FrameBuffer | None:
        return self.get_analysis_buffer(camera_id)

    def get_main_buffer(self, camera_id: str) -> FrameBuffer | None:
        runtime = self.get_runtime(camera_id)
        return runtime.main_frame_buffer if runtime else None

    def get_display_buffer(self, camera_id: str) -> FrameBuffer | None:
        runtime = self.get_runtime(camera_id)
        if runtime is None:
            return None
        return self._select_display_buffer(runtime)

    def display_state(self, camera_id: str) -> tuple[str, bool]:
        runtime = self.get_runtime(camera_id)
        if runtime is None:
            return "single", False
        self._select_display_buffer(runtime)
        return runtime.display_source_current, runtime.display_fallback_active

    def get_analysis_buffer(self, camera_id: str) -> FrameBuffer | None:
        runtime = self.get_runtime(camera_id)
        return runtime.analysis_frame_buffer if runtime else None

    def list_runtimes(self) -> list[CameraRuntime]:
        with self._lock:
            return list(self._runtimes.values())

    def worker_status(self, camera_id: str) -> CaptureWorkerStatus | None:
        runtime = self.get_runtime(camera_id)
        return runtime.analysis_worker.status() if runtime and runtime.analysis_worker else None

    def main_worker_status(self, camera_id: str) -> CaptureWorkerStatus | None:
        runtime = self.get_runtime(camera_id)
        return runtime.main_worker.status() if runtime and runtime.main_worker else None

    def analysis_worker_status(self, camera_id: str) -> CaptureWorkerStatus | None:
        runtime = self.get_runtime(camera_id)
        return runtime.analysis_worker.status() if runtime and runtime.analysis_worker else None

    def stop_all(self) -> None:
        for runtime in self.list_runtimes():
            self._stop_runtime(runtime)
        with self._lock:
            self._runtimes.clear()

    def _create_runtime(self, config: CameraSourceConfig) -> CameraRuntime:
        if not self.settings.enable_dual_stream:
            buffer = FrameBuffer(config.camera_id)
            worker = self._create_worker(config, buffer)
            return CameraRuntime(config=config, frame_buffer=buffer, worker=worker)

        main_url = config.main_source_url or self.settings.main_stream_url or config.source_url
        analysis_url = (
            config.analysis_source_url
            or self.settings.analysis_stream_url
            or self.settings.default_rtsp_url
            or config.source_url
        )
        main_config = CameraSourceConfig(
            camera_id=f"{config.camera_id}:main",
            source_url=main_url,
            output_height=self.settings.main_capture_process_output_height,
            jpeg_quality=self.settings.main_capture_jpeg_quality,
            write_fps=self.settings.main_capture_process_write_fps,
        )
        analysis_config = CameraSourceConfig(
            camera_id=f"{config.camera_id}:analysis",
            source_url=analysis_url,
        )
        main_buffer = FrameBuffer(config.camera_id)
        analysis_buffer = FrameBuffer(config.camera_id)
        main_worker = self._create_worker(main_config, main_buffer, backend=self.settings.main_capture_backend)
        analysis_worker = self._create_worker(
            analysis_config,
            analysis_buffer,
            backend=self.settings.analysis_capture_backend,
        )
        return CameraRuntime(
            config=CameraSourceConfig(
                camera_id=config.camera_id,
                source_url=analysis_url,
                main_source_url=main_url,
                analysis_source_url=analysis_url,
            ),
            frame_buffer=analysis_buffer,
            worker=analysis_worker,
            main_frame_buffer=main_buffer,
            analysis_frame_buffer=analysis_buffer,
            main_worker=main_worker,
            analysis_worker=analysis_worker,
            main_config=main_config,
            analysis_config=analysis_config,
            dual_stream_enabled=True,
        )

    @staticmethod
    def _start_runtime(runtime: CameraRuntime) -> None:
        if runtime.dual_stream_enabled:
            if runtime.main_worker:
                runtime.main_worker.start()
            if runtime.analysis_worker:
                runtime.analysis_worker.start()
            return
        runtime.worker.start()

    @staticmethod
    def _stop_runtime(runtime: CameraRuntime) -> None:
        if runtime.dual_stream_enabled:
            if runtime.main_worker:
                runtime.main_worker.stop()
            if runtime.analysis_worker and runtime.analysis_worker is not runtime.main_worker:
                runtime.analysis_worker.stop()
            return
        runtime.worker.stop()

    def _create_worker(
        self,
        config: CameraSourceConfig,
        buffer: FrameBuffer,
        backend: str | None = None,
    ) -> CaptureWorker | SubprocessCaptureWorker:
        selected_backend = backend or self.settings.capture_backend
        if (
            selected_backend == "subprocess_opencv"
            and not config.source_url.startswith("mock://")
        ):
            return SubprocessCaptureWorker(config, buffer, self.settings)
        return CaptureWorker(config, buffer, self.settings)

    def _select_display_buffer(self, runtime: CameraRuntime) -> FrameBuffer | None:
        if not runtime.dual_stream_enabled:
            runtime.display_source_current = "single"
            runtime.display_fallback_active = False
            return runtime.main_frame_buffer

        if not self.settings.display_fallback_to_analysis:
            runtime.display_source_current = "main"
            runtime.display_fallback_active = False
            return runtime.main_frame_buffer

        main_status = runtime.main_worker.status() if runtime.main_worker else None
        analysis_status = runtime.analysis_worker.status() if runtime.analysis_worker else None
        main_healthy = self._is_display_stream_healthy(main_status)
        analysis_healthy = self._is_display_stream_healthy(analysis_status)
        now = time.monotonic()

        if runtime.display_fallback_active:
            hold_ms = self.settings.display_fallback_min_hold_ms
            held_ms = (
                (now - runtime.display_fallback_since_monotonic) * 1000
                if runtime.display_fallback_since_monotonic is not None
                else hold_ms
            )
            if main_healthy and held_ms >= hold_ms:
                runtime.display_fallback_active = False
                runtime.display_fallback_since_monotonic = None
                runtime.display_source_current = "main"
                return runtime.main_frame_buffer
            runtime.display_source_current = "analysis" if analysis_healthy else "main"
            return runtime.analysis_frame_buffer if analysis_healthy else runtime.main_frame_buffer

        if not main_healthy and analysis_healthy:
            runtime.display_fallback_active = True
            runtime.display_fallback_since_monotonic = now
            runtime.display_source_current = "analysis"
            return runtime.analysis_frame_buffer

        runtime.display_source_current = "main"
        runtime.display_fallback_active = False
        return runtime.main_frame_buffer

    def _is_display_stream_healthy(self, status: CaptureWorkerStatus | None) -> bool:
        if status is None:
            return False
        if not status.running or not status.connected:
            return False
        if status.stream_state != "connected":
            return False
        if status.frame_age_ms is None:
            return False
        return status.frame_age_ms <= self.settings.display_fallback_frame_age_ms
