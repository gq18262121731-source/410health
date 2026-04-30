from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from backend.config import Settings
from backend.services.camera_service import CameraService


logger = logging.getLogger(__name__)

FallEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class FallDetectionService:
    """Runs the external fall-detection model and streams JSONL events back."""

    def __init__(self, settings: Settings, on_event: FallEventHandler) -> None:
        self._settings = settings
        self._on_event = on_event
        self._task: asyncio.Task[None] | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._last_event: dict[str, Any] | None = None
        self._last_event_at: float | None = None
        self._last_error: str | None = None
        self._started_at: float | None = None
        self._restart_count = 0
        self._stopping = False

    async def start(self) -> None:
        if not self._settings.fall_detection_enabled:
            return
        if self._task and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._stopping = True
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    def status(self) -> dict[str, Any]:
        process_running = bool(self._process and self._process.returncode is None)
        return {
            "enabled": self._settings.fall_detection_enabled,
            "running": bool(self._task and not self._task.done()),
            "process_running": process_running,
            "pid": self._process.pid if self._process else None,
            "speed_profile": self._settings.fall_detection_speed_profile,
            "accuracy_preserving": self._settings.fall_detection_speed_profile == "accuracy",
            "event_log": self._settings.fall_detection_event_log,
            "snapshot_dir": self._settings.fall_detection_snapshot_dir,
            "roi": {
                "enabled": self._settings.fall_detection_roi_enabled,
                "rect": self._settings.fall_detection_roi_rect,
                "min_overlap": self._settings.fall_detection_roi_min_overlap,
                "frame_width": self._settings.fall_detection_frame_width,
                "frame_height": self._settings.fall_detection_frame_height,
                "min_alert_score": self._settings.fall_detection_min_alert_score,
            },
            "last_event_at": self._last_event_at,
            "last_event": self._last_event,
            "last_error": self._last_error,
            "restart_count": self._restart_count,
            "started_at": self._started_at,
        }

    async def _run_forever(self) -> None:
        while not self._stopping:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - background supervisor must survive.
                self._last_error = f"{exc.__class__.__name__}: {exc}"
                logger.warning("Fall detection worker failed: %s", self._last_error)

            if not self._stopping:
                self._restart_count += 1
                await asyncio.sleep(max(1.0, self._settings.fall_detection_restart_delay_seconds))

    async def _run_once(self) -> None:
        root = Path(self._settings.fall_detection_model_root)
        python = Path(self._settings.fall_detection_python)
        event_log = Path(self._settings.fall_detection_event_log)
        snapshot_dir = Path(self._settings.fall_detection_snapshot_dir)
        event_log.parent.mkdir(parents=True, exist_ok=True)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        event_log.write_text("", encoding="utf-8")

        rtsp_url = CameraService(self._settings).rtsp_url
        cmd = [
            str(python),
            str(root / "scripts" / "realtime_fall_monitor.py"),
            "--source",
            rtsp_url,
            "--profile",
            self._settings.fall_detection_profile,
            "--event-log",
            str(event_log),
            "--snapshot-dir",
            str(snapshot_dir),
            "--status-log-interval",
            str(self._settings.fall_detection_status_log_interval_seconds),
            "--no-display",
        ]
        cmd.extend(self._speed_profile_args())

        env = os.environ.copy()
        env.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|fflags;nobuffer|max_delay;0")
        self._started_at = time.time()
        self._last_error = None
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(root),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        tail_task = asyncio.create_task(self._tail_events(event_log))
        stderr_task = asyncio.create_task(self._collect_stderr(self._process))
        try:
            returncode = await self._process.wait()
            if returncode not in (0, None) and not self._stopping:
                self._last_error = f"FALL_DETECTION_EXIT_{returncode}"
        finally:
            tail_task.cancel()
            stderr_task.cancel()
            for task in (tail_task, stderr_task):
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def _speed_profile_args(self) -> list[str]:
        profile = self._settings.fall_detection_speed_profile
        if profile == "accuracy":
            return []
        if profile == "balanced":
            return ["--analysis-width", "960", "--process-every", "1", "--device", "0"]
        return ["--analysis-width", "640", "--process-every", "2", "--device", "0", "--half"]

    async def _tail_events(self, event_log: Path) -> None:
        position = 0
        while True:
            if event_log.exists():
                with event_log.open("r", encoding="utf-8") as file:
                    file.seek(position)
                    while True:
                        line = file.readline()
                        if not line:
                            break
                        position = file.tell()
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        self._last_event = event
                        self._last_event_at = time.time()
                        await self._on_event(event)
            await asyncio.sleep(0.35)

    async def _collect_stderr(self, process: asyncio.subprocess.Process) -> None:
        if process.stderr is None:
            return
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                self._last_error = text[-800:]
