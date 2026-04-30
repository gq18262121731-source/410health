from __future__ import annotations

import os
import subprocess
from pathlib import Path

import imageio_ffmpeg


ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    values = dict(os.environ)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values.setdefault(key.strip(), value.strip())
    return values


def build_url(env: dict[str, str], path: str) -> str:
    ip = env.get("CAMERA_IP", "192.168.8.253").strip()
    user = env.get("CAMERA_USER", "admin").strip()
    password = env.get("CAMERA_PASSWORD", "")
    port = env.get("CAMERA_RTSP_PORT", "10554").strip()
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"rtsp://{user}:{password}@{ip}:{port}{normalized_path}"


def mask_url(url: str, password: str) -> str:
    return url.replace(password, "***") if password else url


def find_audio_lines(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if " Audio: " in line]


def probe_url(url: str, password: str) -> tuple[list[str], str]:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        "8000000",
        "-i",
        url,
        "-t",
        "1",
        "-vn",
        "-f",
        "null",
        "-",
    ]
    print(f"\nTesting audio track: {mask_url(url, password)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12, check=False)
    stderr = mask_url(result.stderr.decode("utf-8", errors="replace"), password)
    return find_audio_lines(stderr), stderr


def main() -> int:
    env = load_env()
    password = env.get("CAMERA_PASSWORD", "")
    if not password:
        print("CAMERA_PASSWORD is missing. Please set it in .env first.")
        return 2

    preferred_path = env.get("CAMERA_STREAM_RTSP_PATH", "/tcp/av0_1")
    paths = list(dict.fromkeys([preferred_path, "/tcp/av0_1", "/tcp/av0_0", "/udp/av0_1", "/udp/av0_0"]))
    found = False
    last_error = ""

    for path in paths:
        try:
            lines, stderr = probe_url(build_url(env, path), password)
        except subprocess.TimeoutExpired:
            print(f"Result path={path}: timeout")
            continue

        if lines:
            found = True
            print(f"Result path={path}: audio supported")
            for line in lines:
                print(f"  {line}")
        else:
            print(f"Result path={path}: no audio track detected")
            last_error = stderr.strip()

    if not found:
        print("\nDiagnosis: no RTSP audio track was detected on the tested paths.")
        if last_error:
            print(f"ffmpeg tail: {last_error[-500:]}")
        print("Next: check the camera app/settings or vendor SDK for microphone/talkback support.")
        return 1

    print("\nDiagnosis: RTSP has an audio track. We can build listen-only audio next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
