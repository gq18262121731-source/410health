from __future__ import annotations

import argparse
import math
import os
import struct
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL_32 = Path(os.environ.get("WINDIR", r"C:\Windows")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
GATEWAY_SCRIPT = ROOT / "scripts" / "camera_lan_talk_gateway.ps1"
MODES = ["pcm_mode1", "pcm_mode0", "pcm_setdata", "encoded_setdata", "encoded_mode0", "encoded_mode1"]


def load_env() -> dict[str, str]:
    env = os.environ.copy()
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def tone_frame(frame_index: int, sample_rate: int, frame_samples: int, freq: float, gain: int) -> bytes:
    data = bytearray()
    base = frame_index * frame_samples
    for index in range(frame_samples):
        sample = int(gain * math.sin(2 * math.pi * freq * ((base + index) / sample_rate)))
        data += struct.pack("<h", sample)
    return bytes(data)


def run_mode(mode: str, seconds: float, gain: int, freq: float) -> int:
    env = load_env()
    log_path = ROOT / "logs" / f"camera_talk_mode_{mode}.log"
    ready_path = ROOT / "tmp_camera_probe" / f"camera_talk_mode_{mode}.ready"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    ready_path.unlink(missing_ok=True)
    env.update(
        {
            "CAMERA_LAN_TALK_LOG": str(log_path),
            "CAMERA_LAN_TALK_READY_FILE": str(ready_path),
            "CAMERA_LAN_TALK_SEND_MODE": mode,
        }
    )
    process = subprocess.Popen(
        [
            str(POWERSHELL_32),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(GATEWAY_SCRIPT),
        ],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 14
        while time.time() < deadline and not ready_path.exists() and process.poll() is None:
            time.sleep(0.2)
        if not ready_path.exists():
            print(f"{mode}: gateway did not become ready, log={log_path}")
            return process.returncode or 2

        print(f"{mode}: READY, sending {seconds:.1f}s test tone. Listen near the camera now.")
        sample_rate = 8000
        frame_samples = 160
        frames = int(seconds * sample_rate / frame_samples)
        assert process.stdin is not None
        for frame_index in range(frames):
            process.stdin.write(tone_frame(frame_index, sample_rate, frame_samples, freq, gain))
            if frame_index % 10 == 0:
                process.stdin.flush()
            time.sleep(frame_samples / sample_rate)
        process.stdin.close()
        process.wait(timeout=8)
        print(f"{mode}: done, log={log_path}")
        return process.returncode or 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        ready_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Try vendor LAN talk sending modes with an audible test tone.")
    parser.add_argument("--mode", choices=MODES, help="Run one mode only.")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--gain", type=int, default=9000)
    parser.add_argument("--freq", type=float, default=880.0)
    args = parser.parse_args()

    modes = [args.mode] if args.mode else MODES
    print("Each mode sends a short tone to the camera speaker. Stop if you hear a clear sound.")
    for mode in modes:
        run_mode(mode, args.seconds, args.gain, args.freq)
        time.sleep(1.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
