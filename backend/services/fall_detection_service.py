from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from backend.config import Settings
from backend.services.camera_service import CameraService


logger = logging.getLogger(__name__)

FallEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class FallDetectionService:
    """Runs the external fall-detection model and tails JSONL events."""

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
        self._python_fallback_logged = False

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
            "profile": self._settings.fall_detection_profile,
            "threshold_override": self._settings.fall_detection_threshold_override,
            "process_every_override": self._settings.fall_detection_process_every_override,
            "alert_rules_path": self._settings.fall_detection_alert_rules_path or None,
            "injury_rules_path": self._settings.fall_detection_injury_rules_path or None,
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
        # Delay the first self-referential HTTP pull until the backend routes are live.
        await asyncio.sleep(2.0)
        while not self._stopping:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = f"{exc.__class__.__name__}: {exc}"
                logger.warning("Fall detection worker failed: %s", self._last_error)

            if not self._stopping:
                self._restart_count += 1
                await asyncio.sleep(max(1.0, self._settings.fall_detection_restart_delay_seconds))

    async def _run_once(self) -> None:
        root = Path(self._settings.fall_detection_model_root)
        python = self._resolve_python()
        script = root / "scripts" / "realtime_fall_monitor.py"
        if not script.exists():
            raise RuntimeError(f"FALL_DETECTION_SCRIPT_NOT_FOUND: {script}")

        event_log = Path(self._settings.fall_detection_event_log)
        snapshot_dir = Path(self._settings.fall_detection_snapshot_dir)
        event_log.parent.mkdir(parents=True, exist_ok=True)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        event_log.write_text("", encoding="utf-8")

        source_url = self._resolve_source_url()
        cmd = self._build_command(source_url=source_url, event_log=event_log, snapshot_dir=snapshot_dir)

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
                detail = self._last_error
                self._last_error = (
                    f"FALL_DETECTION_EXIT_{returncode}: {detail}"
                    if detail
                    else f"FALL_DETECTION_EXIT_{returncode}"
                )
        finally:
            tail_task.cancel()
            stderr_task.cancel()
            for task in (tail_task, stderr_task):
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def _resolve_source_url(self) -> str:
        service = CameraService(self._settings)
        active_stream_url = (
            f"http://127.0.0.1:{self._settings.port}"
            f"{self._settings.api_v1_prefix}/camera-sources/active/stream.mjpg"
        )
        if service.resolved_source_mode() == "local":
            return active_stream_url
        runtime = service.runtime_health()
        if runtime and runtime.get("running"):
            return "http://127.0.0.1:8090/api/v1/camera/stream.mjpg"
        if service.resolved_source_mode() == "rtsp":
            urls = service.stream_rtsp_urls
            if urls:
                return urls[0]
        return active_stream_url

    def _build_command(self, *, source_url: str, event_log: Path, snapshot_dir: Path) -> list[str]:
        root = Path(self._settings.fall_detection_model_root)
        python = self._resolve_python()
        command = [
            str(python),
            str(root / "scripts" / "realtime_fall_monitor.py"),
            "--source",
            source_url,
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
        model_registry_path = str(self._settings.fall_detection_model_registry_path or "").strip()
        if model_registry_path:
            command.extend(["--model-registry", model_registry_path])
        threshold_override = float(self._settings.fall_detection_threshold_override or 0.0)
        if threshold_override > 0:
            command.extend(["--threshold", str(threshold_override)])

        alert_rules_path = str(self._settings.fall_detection_alert_rules_path or "").strip()
        if alert_rules_path:
            command.extend(["--alert-rules", alert_rules_path])

        injury_rules_path = str(self._settings.fall_detection_injury_rules_path or "").strip()
        if injury_rules_path:
            command.extend(["--injury-rules", injury_rules_path])

        command.extend(self._speed_profile_args())
        return command

    def _resolve_python(self) -> Path:
        configured = Path(str(self._settings.fall_detection_python or "").strip())
        if configured.exists():
            return configured
        current = Path(sys.executable)
        if current.exists():
            if not self._python_fallback_logged:
                logger.warning(
                    "Configured fall detection Python is unavailable, using current interpreter: %s -> %s",
                    configured,
                    current,
                )
                self._python_fallback_logged = True
            return current
        raise RuntimeError(f"FALL_DETECTION_PYTHON_NOT_FOUND: {configured}")

    def _speed_profile_args(self) -> list[str]:
        override = int(self._settings.fall_detection_process_every_override or 0)
        if override > 0:
            return ["--process-every", str(override)]
        profile = self._settings.fall_detection_speed_profile
        if profile == "accuracy":
            return []
        if profile == "balanced":
            return ["--process-every", "2"]
        return ["--process-every", "3"]

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
                        event["_observed_at"] = time.time()
                        self._last_event = event
                        self._last_event_at = time.time()
                        try:
                            await self._on_event(event)
                        except Exception as exc:
                            self._last_error = f"{exc.__class__.__name__}: {exc}"
                            logger.exception("Fall detection event handler failed: %s", self._last_error)
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
