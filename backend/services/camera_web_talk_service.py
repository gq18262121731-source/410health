from __future__ import annotations

import time
import os
import subprocess
from pathlib import Path
from threading import Lock

from backend.config import BASE_DIR, Settings


class CameraWebTalkService:
    """Receives browser microphone PCM for the future vendor TalkData bridge."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._active = False
        self._started_at: float | None = None
        self._last_chunk_at: float | None = None
        self._bytes_received = 0
        self._chunks_received = 0
        self._peak_level = 0
        self._record_file: Path | None = None
        self._record_handle = None
        self._gateway_process: subprocess.Popen[bytes] | None = None
        self._gateway_error: str | None = None
        self._gateway_log = BASE_DIR / "logs" / "camera_lan_talk_gateway.log"
        self._gateway_ready_file = BASE_DIR / "tmp_camera_probe" / "camera_lan_talk_gateway.ready"

    def start(self) -> dict[str, object]:
        with self._lock:
            self._close_record_handle()
            now = time.time()
            record_dir = BASE_DIR / "tmp_camera_probe"
            record_dir.mkdir(parents=True, exist_ok=True)
            self._record_file = record_dir / f"web_talk_{int(now)}_pcm16_8k_mono.pcm"
            self._record_handle = self._record_file.open("ab")
            self._active = True
            self._started_at = now
            self._last_chunk_at = None
            self._bytes_received = 0
            self._chunks_received = 0
            self._peak_level = 0
            self._start_gateway()
            return self.status()

    def receive_pcm(self, chunk: bytes) -> dict[str, object]:
        if not chunk:
            return self.status()

        with self._lock:
            if not self._active:
                now = time.time()
                record_dir = BASE_DIR / "tmp_camera_probe"
                record_dir.mkdir(parents=True, exist_ok=True)
                self._record_file = record_dir / f"web_talk_{int(now)}_pcm16_8k_mono.pcm"
                self._record_handle = self._record_file.open("ab")
                self._active = True
                self._started_at = now
                self._bytes_received = 0
                self._chunks_received = 0
                self._peak_level = 0
                self._start_gateway()
            self._bytes_received += len(chunk)
            self._chunks_received += 1
            self._last_chunk_at = time.time()
            self._peak_level = max(self._peak_level, self._pcm16_peak(chunk))
            if self._record_handle:
                self._record_handle.write(chunk)
                if self._chunks_received % 25 == 0:
                    self._record_handle.flush()
            gateway_state = self._read_gateway_state()
            if gateway_state["device_talk_ready"]:
                self._write_gateway(chunk)
            else:
                self._refresh_gateway_process_state()
            return self.status()

    def stop(self) -> dict[str, object]:
        with self._lock:
            self._active = False
            self._stop_gateway()
            self._close_record_handle()
            return self.status()

    def status(self) -> dict[str, object]:
        running = self._active
        elapsed = time.time() - self._started_at if running and self._started_at else 0
        bitrate = (self._bytes_received * 8 / elapsed) if elapsed > 0 else 0
        gateway_state = self._read_gateway_state()
        gateway_alive = bool(self._gateway_process and self._gateway_process.poll() is None)
        device_talk_ready = gateway_state["device_talk_ready"]
        delivery_state = "idle"
        if running:
            if device_talk_ready:
                delivery_state = "device_talk_ready"
            elif self._gateway_error or gateway_state["gateway_error"]:
                delivery_state = "gateway_failed"
            elif gateway_alive:
                delivery_state = "gateway_connecting"
            else:
                delivery_state = "recording_only"
        return {
            "running": running,
            "mode": "web_microphone_pcm_to_lan_vendor_gateway",
            "delivery_state": delivery_state,
            "sample_rate": self._settings.camera_audio_sample_rate,
            "channels": 1,
            "sample_format": "pcm_s16le",
            "bytes_received": self._bytes_received,
            "chunks_received": self._chunks_received,
            "elapsed_seconds": round(elapsed, 2),
            "throughput_kbps": round(bitrate / 1000, 2),
            "peak_level": self._peak_level,
            "last_chunk_at": self._last_chunk_at,
            "record_file": str(self._record_file) if self._record_file else None,
            "gateway_ready": gateway_alive,
            "gateway_pid": self._gateway_process.pid if self._gateway_process else None,
            "gateway_error": gateway_state["gateway_error"] or self._gateway_error,
            "gateway_last_message": gateway_state["last_message"],
            "p2p_status": gateway_state["p2p_status"],
            "device_talk_ready": device_talk_ready,
            "gateway_log": str(self._gateway_log),
            "note": "Browser microphone PCM is received by the backend, encoded with the vendor LAN SDK, and forwarded to the camera talk channel.",
        }

    def _close_record_handle(self) -> None:
        if self._record_handle:
            self._record_handle.close()
            self._record_handle = None

    def _start_gateway(self) -> None:
        self._stop_gateway()
        self._gateway_error = None
        if not self._settings.camera_password:
            self._gateway_error = "CAMERA_PASSWORD_NOT_CONFIGURED"
            return
        if not self._settings.camera_ip.strip():
            self._gateway_error = "CAMERA_IP_NOT_CONFIGURED"
            return

        script = BASE_DIR / "scripts" / "camera_lan_talk_gateway.ps1"
        powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        dll_dir = Path(r"C:\Program Files (x86)\IPCam ActiveX\924")
        if not powershell.exists():
            self._gateway_error = "POWERSHELL_32BIT_NOT_FOUND"
            return
        if not script.exists():
            self._gateway_error = "CAMERA_LAN_TALK_GATEWAY_SCRIPT_NOT_FOUND"
            return
        if not (dll_dir / "DevDll_924.dll").exists():
            self._gateway_error = f"DEV_DLL_924_NOT_FOUND: {dll_dir}"
            return

        self._gateway_log.parent.mkdir(parents=True, exist_ok=True)
        self._gateway_ready_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._gateway_log.write_text("", encoding="utf-8")
        except OSError:
            pass
        try:
            self._gateway_ready_file.unlink(missing_ok=True)
        except OSError:
            pass
        env = os.environ.copy()
        env.update(
            {
                "CAMERA_P2P_DLL_DIR": str(dll_dir),
                "CAMERA_LAN_TALK_DLL_DIR": str(dll_dir),
                "CAMERA_IP": self._settings.camera_ip.strip(),
                "CAMERA_ONVIF_PORT": str(self._settings.camera_onvif_port),
                "CAMERA_USER": self._settings.camera_user.strip(),
                "CAMERA_PASSWORD": self._settings.camera_password,
                "CAMERA_LAN_TALK_LOG": str(self._gateway_log),
                "CAMERA_LAN_TALK_READY_FILE": str(self._gateway_ready_file),
            }
        )
        try:
            self._gateway_process = subprocess.Popen(
                [
                    str(powershell),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                cwd=str(BASE_DIR),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            self._gateway_error = f"{exc.__class__.__name__}: {exc}"
            self._gateway_process = None

    def _write_gateway(self, chunk: bytes) -> None:
        process = self._gateway_process
        if not process:
            return
        if process.poll() is not None:
            self._gateway_error = f"LAN_TALK_GATEWAY_EXITED:{process.returncode}"
            self._gateway_process = None
            return
        if not process.stdin:
            self._gateway_error = "LAN_TALK_GATEWAY_STDIN_NOT_AVAILABLE"
            return
        try:
            process.stdin.write(chunk)
            if self._chunks_received % 20 == 0:
                process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._gateway_error = f"{exc.__class__.__name__}: {exc}"
            self._gateway_process = None

    def _refresh_gateway_process_state(self) -> None:
        process = self._gateway_process
        if not process:
            return
        return_code = process.poll()
        if return_code is not None:
            self._gateway_error = f"LAN_TALK_GATEWAY_EXITED:{return_code}"
            self._gateway_process = None

    def _stop_gateway(self) -> None:
        process = self._gateway_process
        self._gateway_process = None
        if not process:
            return
        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        try:
            self._gateway_ready_file.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _pcm16_peak(chunk: bytes) -> int:
        peak = 0
        limit = len(chunk) - (len(chunk) % 2)
        for index in range(0, limit, 2):
            sample = int.from_bytes(chunk[index : index + 2], byteorder="little", signed=True)
            peak = max(peak, abs(sample))
        return min(100, round(peak / 32767 * 100))

    def _read_gateway_state(self) -> dict[str, object]:
        state: dict[str, object] = {
            "device_talk_ready": self._gateway_ready_file.exists(),
            "gateway_error": None,
            "last_message": None,
            "p2p_status": None,
            "encoded_frames": None,
        }
        if not self._gateway_log.exists():
            return state

        try:
            lines = self._gateway_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-240:]
        except OSError:
            return state

        for line in reversed(lines):
            if state["last_message"] is None and line.strip():
                state["last_message"] = line.strip()
            if state["gateway_error"] is None and "LAN_TALK_GATEWAY_ERROR=" in line:
                state["gateway_error"] = line.split("LAN_TALK_GATEWAY_ERROR=", 1)[-1].strip()
            if "LAN_TALK_READY" in line:
                state["device_talk_ready"] = True
                break
        return state
