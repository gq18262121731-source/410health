from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp_rtsp_camera1_debug"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_first(env: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = env.get(key, "").strip()
        if value:
            return value
    return default


def build_rtsp_url(env: dict[str, str], path: str | None = None, port: int | None = None) -> str:
    ip = get_first(env, "CAMERA1_IP", "CAMERA_IP")
    user = get_first(env, "CAMERA1_USER", "CAMERA_USER", default="admin")
    password = get_first(env, "CAMERA1_PASSWORD", "CAMERA_PASSWORD")
    rtsp_port = port or int(get_first(env, "CAMERA1_RTSP_PORT", "CAMERA_RTSP_PORT", default="10554"))
    rtsp_path = (path or get_first(env, "CAMERA1_STREAM_RTSP_PATH", "CAMERA_STREAM_RTSP_PATH", default="/tcp/av0_1")).strip()
    if not rtsp_path.startswith("/"):
        rtsp_path = f"/{rtsp_path}"
    return f"rtsp://{user}:{password}@{ip}:{rtsp_port}{rtsp_path}"


def mask_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    prefix, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" not in creds:
        return url
    user, _password = creds.split(":", 1)
    return f"{prefix}://{user}:***@{host}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal ffmpeg RTSP first-frame validation.")
    parser.add_argument("--url", help="Full RTSP URL. Defaults to CAMERA1/CAMERA env values.")
    parser.add_argument("--path", help="Override RTSP path, e.g. /tcp/av0_1")
    parser.add_argument("--port", type=int, help="Override RTSP port")
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    parser.add_argument("--ffmpeg-loglevel", default="error")
    args = parser.parse_args()

    env = load_env()
    url = args.url or build_rtsp_url(env, path=args.path, port=args.port)
    transport = "udp" if "/udp/" in url.lower() else "tcp"

    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise SystemExit(f"imageio_ffmpeg not installed: {exc}") from exc

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUT_DIR / "debug_first_frame.jpg"

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        args.ffmpeg_loglevel,
        "-nostdin",
        "-fflags",
        "discardcorrupt",
        "-probesize",
        "5000000",
        "-analyzeduration",
        "1000000",
        "-rtsp_transport",
        transport,
        "-timeout",
        str(int(args.timeout_seconds * 1_000_000)),
        "-i",
        url,
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-",
    ]

    started_at = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout_seconds + 4,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        payload = {
            "ok": False,
            "stage": "subprocess_timeout",
            "url": mask_url(url),
            "transport": transport,
            "timeout_seconds": args.timeout_seconds,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 1),
            "error": f"TimeoutExpired: {exc}",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
    stdout = result.stdout or b""
    stderr_text = (result.stderr or b"").decode("utf-8", errors="replace").strip()
    is_jpeg = stdout.startswith(b"\xff\xd8") and stdout.endswith(b"\xff\xd9")

    if is_jpeg:
        output_path.write_bytes(stdout)

    payload = {
        "ok": bool(is_jpeg and result.returncode == 0),
        "stage": "first_frame",
        "url": mask_url(url),
        "transport": transport,
        "ffmpeg": ffmpeg,
        "returncode": result.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout_bytes": len(stdout),
        "stderr_tail": stderr_text[-500:] if stderr_text else "",
        "saved": str(output_path) if is_jpeg else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
