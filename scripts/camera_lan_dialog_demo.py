from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL_32 = Path(os.environ.get("WINDIR", r"C:\Windows")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
GATEWAY_SCRIPT = ROOT / "scripts" / "camera_lan_talk_gateway.ps1"
DEFAULT_PYTHON = Path(r"C:\Users\13010\anaconda3\envs\helth\python.exe")
FRAME_BYTES = 320
SAMPLE_RATE = 8000


def load_env() -> dict[str, str]:
    env = os.environ.copy()
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def mask_secret(text: str, env: dict[str, str]) -> str:
    password = env.get("CAMERA_PASSWORD", "")
    return text.replace(password, "***") if password else text


def run_script(script: str, env: dict[str, str], timeout: int) -> int:
    python_exe = DEFAULT_PYTHON if DEFAULT_PYTHON.exists() else Path(sys.executable)
    cmd = [str(python_exe), str(ROOT / "scripts" / script)]
    print(f"RUN {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    print(mask_secret(result.stdout, env))
    return result.returncode


def tone_frame(frame_index: int, seconds_per_frame: float, freq: float, gain: int) -> bytes:
    samples = FRAME_BYTES // 2
    start_sample = int(frame_index * seconds_per_frame * SAMPLE_RATE)
    data = bytearray()
    for index in range(samples):
        t = (start_sample + index) / SAMPLE_RATE
        sample = int(gain * math.sin(2 * math.pi * freq * t))
        data += sample.to_bytes(2, byteorder="little", signed=True)
    return bytes(data)


def start_gateway(env: dict[str, str], send_mode: str, log_name: str, ready_name: str) -> tuple[subprocess.Popen[bytes], Path, Path]:
    if not POWERSHELL_32.exists():
        raise RuntimeError(f"32-bit PowerShell not found: {POWERSHELL_32}")
    if not GATEWAY_SCRIPT.exists():
        raise RuntimeError(f"Gateway script not found: {GATEWAY_SCRIPT}")

    log_path = ROOT / "logs" / log_name
    ready_path = ROOT / "tmp_camera_probe" / ready_name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")
    ready_path.unlink(missing_ok=True)

    child_env = env.copy()
    child_env.update(
        {
            "CAMERA_LAN_TALK_LOG": str(log_path),
            "CAMERA_LAN_TALK_READY_FILE": str(ready_path),
            "CAMERA_LAN_TALK_SEND_MODE": send_mode,
        }
    )
    if not child_env.get("CAMERA_LAN_TALK_DLL_DIR"):
        child_env["CAMERA_LAN_TALK_DLL_DIR"] = child_env.get("CAMERA_P2P_DLL_DIR", r"C:\Program Files (x86)\IPCam ActiveX\924")

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
        env=child_env,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process, log_path, ready_path


def wait_gateway_ready(process: subprocess.Popen[bytes], ready_path: Path, log_path: Path, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ready_path.exists():
            return
        if process.poll() is not None:
            log_tail = log_path.read_text(encoding="utf-8", errors="ignore")[-1200:] if log_path.exists() else ""
            raise RuntimeError(f"LAN talk gateway exited early: {process.returncode}\n{log_tail}")
        time.sleep(0.2)
    log_tail = log_path.read_text(encoding="utf-8", errors="ignore")[-1200:] if log_path.exists() else ""
    raise RuntimeError(f"LAN talk gateway was not ready in {timeout:.1f}s\n{log_tail}")


def stop_gateway(process: subprocess.Popen[bytes], ready_path: Path) -> None:
    try:
        if process.stdin:
            process.stdin.close()
    except OSError:
        pass
    try:
        process.wait(timeout=6)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
    ready_path.unlink(missing_ok=True)


def run_tone(env: dict[str, str], seconds: float, send_mode: str, gain: int, freq: float) -> int:
    process, log_path, ready_path = start_gateway(
        env,
        send_mode,
        f"camera_lan_dialog_tone_{send_mode}.log",
        f"camera_lan_dialog_tone_{send_mode}.ready",
    )
    try:
        wait_gateway_ready(process, ready_path, log_path, 16)
        print(f"READY: sending {seconds:.1f}s tone to the camera speaker, mode={send_mode}, log={log_path}")
        assert process.stdin is not None
        frame_seconds = (FRAME_BYTES // 2) / SAMPLE_RATE
        frame_count = int(seconds / frame_seconds)
        for frame_index in range(frame_count):
            process.stdin.write(tone_frame(frame_index, frame_seconds, freq, gain))
            if frame_index % 10 == 0:
                process.stdin.flush()
            time.sleep(frame_seconds)
        return 0
    finally:
        stop_gateway(process, ready_path)
        print(f"DONE: gateway log is {log_path}")


def get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
    except ModuleNotFoundError as exc:
        raise RuntimeError("imageio_ffmpeg is missing. Run this demo with the helth Python env or install imageio-ffmpeg.") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def list_dshow_audio_devices(ffmpeg: str) -> list[str]:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    devices: list[str] = []
    for line in result.stderr.splitlines():
        match = re.search(r'\[dshow[^\]]*\]\s+"(.+)"\s+\(audio\)', line)
        if match:
            devices.append(match.group(1))
    return devices


def run_mic(env: dict[str, str], seconds: float, send_mode: str, audio_device: str | None) -> int:
    ffmpeg = get_ffmpeg_exe()
    devices = list_dshow_audio_devices(ffmpeg)
    selected_device = audio_device or env.get("CAMERA_TALK_MIC_DEVICE") or (devices[0] if devices else "")
    if not selected_device:
        raise RuntimeError("No DirectShow audio input device found. Run ffmpeg -list_devices true -f dshow -i dummy to inspect devices.")

    process, log_path, ready_path = start_gateway(
        env,
        send_mode,
        f"camera_lan_dialog_mic_{send_mode}.log",
        f"camera_lan_dialog_mic_{send_mode}.ready",
    )
    ffmpeg_process: subprocess.Popen[bytes] | None = None
    try:
        wait_gateway_ready(process, ready_path, log_path, 16)
        print(f"READY: streaming microphone '{selected_device}' for {seconds:.1f}s, mode={send_mode}")
        assert process.stdin is not None
        ffmpeg_process = subprocess.Popen(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "warning",
                "-f",
                "dshow",
                "-i",
                f"audio={selected_device}",
                "-t",
                str(seconds),
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(SAMPLE_RATE),
                "-ac",
                "1",
                "-f",
                "s16le",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert ffmpeg_process.stdout is not None
        while True:
            chunk = ffmpeg_process.stdout.read(4096)
            if not chunk:
                break
            process.stdin.write(chunk)
        if process.stdin:
            process.stdin.flush()
        stderr = ffmpeg_process.stderr.read().decode("utf-8", errors="replace") if ffmpeg_process.stderr else ""
        code = ffmpeg_process.wait(timeout=5)
        if code != 0:
            print(mask_secret(stderr, env))
            return code
        return 0
    finally:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            ffmpeg_process.kill()
            ffmpeg_process.wait(timeout=3)
        stop_gateway(process, ready_path)
        print(f"DONE: gateway log is {log_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="LAN camera dialog demo: ONVIF/RTSP probe, speaker tone, and microphone talkback.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe", help="Probe ONVIF audio output support and RTSP microphone audio tracks.")

    tone = subparsers.add_parser("tone", help="Send a short test tone to the camera speaker through the vendor LAN gateway.")
    tone.add_argument("--seconds", type=float, default=3.0)
    tone.add_argument("--send-mode", default="pcm_mode1")
    tone.add_argument("--gain", type=int, default=9000)
    tone.add_argument("--freq", type=float, default=880.0)

    mic = subparsers.add_parser("mic", help="Stream the Windows default microphone to the camera speaker.")
    mic.add_argument("--seconds", type=float, default=10.0)
    mic.add_argument("--send-mode", default="pcm_mode1")
    mic.add_argument("--audio-device", help="DirectShow microphone name. Defaults to CAMERA_TALK_MIC_DEVICE or the first audio device.")

    args = parser.parse_args()
    env = load_env()
    if args.command == "probe":
        onvif_code = run_script("camera_onvif_talk_probe.py", env, 40)
        audio_code = run_script("camera_audio_probe.py", env, 40)
        return 0 if onvif_code == 0 and audio_code == 0 else 1
    if args.command == "tone":
        return run_tone(env, args.seconds, args.send_mode, args.gain, args.freq)
    if args.command == "mic":
        return run_mic(env, args.seconds, args.send_mode, args.audio_device)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
