from __future__ import annotations

import os
import subprocess
import time
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


def mask_url(url: str, password: str) -> str:
    return url.replace(password, "***") if password else url


def build_url(env: dict[str, str], path: str) -> str:
    ip = env.get("CAMERA_IP", "192.168.8.253").strip()
    user = env.get("CAMERA_USER", "admin").strip()
    password = env.get("CAMERA_PASSWORD", "")
    port = env.get("CAMERA_RTSP_PORT", "10554").strip()
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"rtsp://{user}:{password}@{ip}:{port}{normalized_path}"


def count_jpegs(buffer: bytes) -> tuple[int, bytes]:
    count = 0
    while True:
        start = buffer.find(b"\xff\xd8")
        end = buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
        if start < 0:
            return count, buffer[-2:]
        if end < 0:
            return count, buffer[start:]
        count += 1
        buffer = buffer[end + 2 :]


def probe_url(url: str, seconds: float, password: str) -> tuple[int, float, str]:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        "8000000",
        "-i",
        url,
        "-an",
        "-q:v",
        "6",
        "-f",
        "mjpeg",
        "-",
    ]
    print(f"\nTesting {mask_url(url, password)}")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    started = time.perf_counter()
    frames = 0
    buffer = b""
    last_error = ""
    try:
        while time.perf_counter() - started < seconds:
            if process.stdout is None:
                break
            chunk = process.stdout.read(8192)
            if not chunk:
                if process.poll() is not None:
                    break
                time.sleep(0.02)
                continue
            found, buffer = count_jpegs(buffer + chunk)
            frames += found
    finally:
        process.kill()
        try:
            _, stderr = process.communicate(timeout=2)
            last_error = stderr.decode("utf-8", errors="replace").strip()
        except Exception:
            pass

    elapsed = max(time.perf_counter() - started, 0.001)
    return frames, frames / elapsed, last_error


def main() -> int:
    env = load_env()
    password = env.get("CAMERA_PASSWORD", "")
    if not password:
        print("CAMERA_PASSWORD is missing. Please set it in .env first.")
        return 2

    seconds = float(env.get("CAMERA_FPS_PROBE_SECONDS", "10"))
    preferred_path = env.get("CAMERA_STREAM_RTSP_PATH", "/tcp/av0_1")
    paths = [preferred_path, "/tcp/av0_1", "/tcp/av0_0"]
    unique_paths = list(dict.fromkeys(paths))

    print(f"Probe duration: {seconds:.1f}s")
    print("Goal: camera RTSP should be close to 24 fps on the stream path.")
    best: tuple[str, int, float] | None = None
    for path in unique_paths:
        frames, fps, error = probe_url(build_url(env, path), seconds, password)
        print(f"Result path={path}: frames={frames}, fps={fps:.2f}")
        if error:
            print(f"ffmpeg: {error[:300]}")
        if best is None or fps > best[2]:
            best = (path, frames, fps)

    if best:
        print(f"\nBEST path={best[0]} frames={best[1]} fps={best[2]:.2f}")
        if best[2] < 20:
            print("Diagnosis: camera/source side is below 24 fps, or RTSP decoding is blocked/slow.")
        else:
            print("Diagnosis: camera/source side can provide near-24fps frames.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
