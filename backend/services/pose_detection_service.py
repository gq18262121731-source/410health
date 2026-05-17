from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from backend.config import Settings
from backend.services.camera_service import CameraService


logger = logging.getLogger(__name__)


class PoseDetectionService:
    """Runs the external pose-detection runtime and tails latest outputs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._last_payload: dict[str, Any] | None = None
        self._last_payload_at: float | None = None
        self._last_error: str | None = None
        self._started_at: float | None = None
        self._restart_count = 0
        self._stopping = False

    async def start(self) -> None:
        if not self._settings.pose_detection_enabled:
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

    def latest(self) -> dict[str, Any] | None:
        return self._last_payload

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    def status(self) -> dict[str, Any]:
        process_running = bool(self._process and self._process.returncode is None)
        source_url = self._resolve_source_url()
        model_root = Path(self._settings.pose_detection_model_root)
        python = Path(self._settings.pose_detection_python)
        return {
            "enabled": self._settings.pose_detection_enabled,
            "running": bool(self._task and not self._task.done()),
            "process_running": process_running,
            "pid": self._process.pid if self._process else None,
            "profile": self._settings.pose_detection_profile,
            "process_every_override": self._settings.pose_detection_process_every_override,
            "pose_conf_threshold": self._settings.pose_detection_pose_conf_threshold,
            "analysis_width": self._settings.pose_detection_analysis_width,
            "event_log": self._settings.pose_detection_event_log,
            "latest_json": self._settings.pose_detection_latest_json,
            "snapshot_dir": self._settings.pose_detection_snapshot_dir,
            "source_mode": self._settings.camera_source_mode,
            "source_url": source_url,
            "model_root": str(model_root),
            "model_root_exists": model_root.exists(),
            "python_command": self._settings.pose_detection_python,
            "python_exists": python.exists() if python.is_absolute() else None,
            "last_payload_at": self._last_payload_at,
            "last_payload": self._last_payload,
            "last_error": self._last_error,
            "restart_count": self._restart_count,
            "started_at": self._started_at,
        }

    async def _run_forever(self) -> None:
        await asyncio.sleep(2.0)
        while not self._stopping:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = f"{exc.__class__.__name__}: {exc}"
                logger.warning("Pose detection worker failed: %s", self._last_error)

            if not self._stopping:
                self._restart_count += 1
                await asyncio.sleep(max(1.0, self._settings.pose_detection_restart_delay_seconds))

    async def _run_once(self) -> None:
        root = Path(self._settings.pose_detection_model_root)
        python = Path(self._settings.pose_detection_python)
        event_log = Path(self._settings.pose_detection_event_log)
        latest_json = Path(self._settings.pose_detection_latest_json)
        snapshot_dir = Path(self._settings.pose_detection_snapshot_dir)
        script_path = root / "scripts" / "realtime_pose_monitor.py"

        if not root.exists():
            raise FileNotFoundError(f"POSE_DETECTION_MODEL_ROOT_NOT_FOUND: {root}")
        if not script_path.is_file():
            raise FileNotFoundError(f"POSE_DETECTION_SCRIPT_NOT_FOUND: {script_path}")
        if python.is_absolute() and not python.exists():
            raise FileNotFoundError(f"POSE_DETECTION_PYTHON_NOT_FOUND: {python}")

        event_log.parent.mkdir(parents=True, exist_ok=True)
        latest_json.parent.mkdir(parents=True, exist_ok=True)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        event_log.write_text("", encoding="utf-8")
        latest_json.write_text("{}", encoding="utf-8")

        source_url = self._resolve_source_url()
        cmd = self._build_command(
            source_url=source_url,
            event_log=event_log,
            latest_json=latest_json,
            snapshot_dir=snapshot_dir,
        )

        env = os.environ.copy()
        env.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|fflags;nobuffer|max_delay;0")
        env.setdefault("YOLO_CONFIG_DIR", str(Path.cwd() / "Ultralytics"))
        self._started_at = time.time()
        self._last_error = None
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(root),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        latest_task = asyncio.create_task(self._tail_latest_json(latest_json))
        stderr_task = asyncio.create_task(self._collect_stderr(self._process))
        try:
            returncode = await self._process.wait()
            if returncode not in (0, None) and not self._stopping:
                self._last_error = f"POSE_DETECTION_EXIT_{returncode}"
        finally:
            latest_task.cancel()
            stderr_task.cancel()
            for task in (latest_task, stderr_task):
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def _resolve_source_url(self) -> str:
        service = CameraService(self._settings)
        runtime = service.runtime_health()
        if runtime and runtime.get("running"):
            return "http://127.0.0.1:8090/api/v1/camera/stream.mjpg"
        if service.resolved_source_mode() == "rtsp":
            urls = service.stream_rtsp_urls
            if urls:
                return urls[0]
        return f"http://127.0.0.1:{self._settings.port}{self._settings.api_v1_prefix}/camera/stream.mjpg"

    def _build_command(
        self,
        *,
        source_url: str,
        event_log: Path,
        latest_json: Path,
        snapshot_dir: Path,
    ) -> list[str]:
        root = Path(self._settings.pose_detection_model_root)
        python = Path(self._settings.pose_detection_python)
        command = [
            str(python),
            str(root / "scripts" / "realtime_pose_monitor.py"),
            "--source",
            source_url,
            "--profile",
            self._settings.pose_detection_profile,
            "--event-log",
            str(event_log),
            "--latest-json",
            str(latest_json),
            "--snapshot-dir",
            str(snapshot_dir),
            "--status-log-interval",
            str(self._settings.pose_detection_status_log_interval_seconds),
            "--pose-conf",
            str(self._settings.pose_detection_pose_conf_threshold),
            "--max-det",
            str(self._settings.pose_detection_track_max_det),
            "--analysis-width",
            str(self._settings.pose_detection_analysis_width),
            "--no-display",
        ]
        process_every = int(self._settings.pose_detection_process_every_override or 0)
        if process_every > 0:
            command.extend(["--process-every", str(process_every)])
        floor_roi = str(self._settings.pose_detection_floor_roi_rect or "").strip()
        if floor_roi:
            command.extend(["--floor-roi", floor_roi])
        return command

    async def _tail_latest_json(self, latest_json: Path) -> None:
        last_mtime_ns = 0
        while True:
            try:
                if latest_json.exists():
                    stat = latest_json.stat()
                    if stat.st_mtime_ns != last_mtime_ns and stat.st_size > 0:
                        raw = latest_json.read_text(encoding="utf-8").strip()
                        last_mtime_ns = stat.st_mtime_ns
                        if raw:
                            payload = json.loads(raw)
                            payload["_observed_at"] = time.time()
                            self._last_payload = payload
                            self._last_payload_at = time.time()
            except json.JSONDecodeError:
                pass
            except Exception as exc:
                self._last_error = f"{exc.__class__.__name__}: {exc}"
            await asyncio.sleep(0.25)

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
