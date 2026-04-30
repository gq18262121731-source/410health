from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from threading import Lock

from backend.config import BASE_DIR, Settings


class CameraTalkService:
    """Controls vendor ActiveX talkback through a 32-bit PowerShell bridge."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._process: subprocess.Popen[str] | None = None
        self._started_at: float | None = None
        self._stop_file = BASE_DIR / "tmp_camera_probe" / "camera_talk.stop"
        self._log_file = BASE_DIR / "logs" / "camera_talk_bridge.log"

    def start(self) -> dict[str, object]:
        with self._lock:
            if self._process and self._process.poll() is None:
                return self.status()

            if not self._settings.camera_password:
                raise RuntimeError("CAMERA_PASSWORD_NOT_CONFIGURED")

            script = BASE_DIR / "scripts" / "camera_activex_talk_bridge.ps1"
            powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            if not powershell.exists():
                raise RuntimeError("POWERSHELL_32BIT_NOT_FOUND")
            if not script.exists():
                raise RuntimeError("CAMERA_TALK_BRIDGE_SCRIPT_NOT_FOUND")

            self._stop_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            if self._stop_file.exists():
                self._stop_file.unlink()

            env = os.environ.copy()
            env.update(
                {
                    "CAMERA_IP": self._settings.camera_ip.strip(),
                    "CAMERA_ACTIVEX_ID": self._settings.camera_activex_id.strip(),
                    "CAMERA_USER": self._settings.camera_user.strip(),
                    "CAMERA_PASSWORD": self._settings.camera_password,
                    "CAMERA_ACTIVEX_PORT": str(self._settings.camera_activex_port),
                    "CAMERA_ACTIVEX_DEV_TYPE": str(self._settings.camera_activex_dev_type),
                    "CAMERA_TALK_MAX_SECONDS": str(self._settings.camera_talk_max_seconds),
                    "CAMERA_TALK_STOP_FILE": str(self._stop_file),
                }
            )

            log_handle = self._log_file.open("a", encoding="utf-8")
            self._process = subprocess.Popen(
                [
                    str(powershell),
                    "-NoProfile",
                    "-Sta",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                cwd=str(BASE_DIR),
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self._started_at = time.time()
            return self.status()

    def stop(self) -> dict[str, object]:
        with self._lock:
            if self._process and self._process.poll() is None:
                self._stop_file.parent.mkdir(parents=True, exist_ok=True)
                self._stop_file.write_text("stop", encoding="utf-8")
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=3)
            return self.status()

    def status(self) -> dict[str, object]:
        process = self._process
        running = bool(process and process.poll() is None)
        return {
            "running": running,
            "pid": process.pid if process else None,
            "started_at": self._started_at,
            "elapsed_seconds": round(time.time() - self._started_at, 2) if running and self._started_at else 0,
            "mode": "activex_local_windows_microphone",
            "active_port": self._settings.camera_activex_port,
            "active_dev_type": self._settings.camera_activex_dev_type,
            "bridge_talking": self._read_bridge_talking(),
            "log_file": str(self._log_file),
            "note": "Uses the Windows backend machine default microphone through the vendor ActiveX control.",
        }

    def _read_bridge_talking(self) -> bool | None:
        if not self._log_file.exists():
            return None

        try:
            lines = self._log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-160:]
        except OSError:
            return None

        for line in reversed(lines):
            match = re.search(r"START_TALK_CALLED.*IsTalking=(\d+)", line)
            if match:
                return match.group(1) != "0"
            if "BRIDGE_ERROR=" in line:
                return False
        return None
