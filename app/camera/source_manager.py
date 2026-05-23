from __future__ import annotations

import threading
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
            buffer = FrameBuffer(config.camera_id)
            worker = self._create_worker(config, buffer)
            runtime = CameraRuntime(config=config, frame_buffer=buffer, worker=worker)
            self._runtimes[config.camera_id] = runtime
            worker.start()
            return runtime, True

    def stop_source(self, camera_id: str) -> bool:
        with self._lock:
            runtime = self._runtimes.pop(camera_id, None)
        if not runtime:
            return False
        runtime.worker.stop()
        return True

    def get_runtime(self, camera_id: str) -> CameraRuntime | None:
        with self._lock:
            return self._runtimes.get(camera_id)

    def get_buffer(self, camera_id: str) -> FrameBuffer | None:
        runtime = self.get_runtime(camera_id)
        return runtime.frame_buffer if runtime else None

    def list_runtimes(self) -> list[CameraRuntime]:
        with self._lock:
            return list(self._runtimes.values())

    def worker_status(self, camera_id: str) -> CaptureWorkerStatus | None:
        runtime = self.get_runtime(camera_id)
        return runtime.worker.status() if runtime else None

    def stop_all(self) -> None:
        for runtime in self.list_runtimes():
            runtime.worker.stop()
        with self._lock:
            self._runtimes.clear()

    def _create_worker(
        self,
        config: CameraSourceConfig,
        buffer: FrameBuffer,
    ) -> CaptureWorker | SubprocessCaptureWorker:
        if (
            self.settings.capture_backend == "subprocess_opencv"
            and not config.source_url.startswith("mock://")
        ):
            return SubprocessCaptureWorker(config, buffer, self.settings)
        return CaptureWorker(config, buffer, self.settings)
