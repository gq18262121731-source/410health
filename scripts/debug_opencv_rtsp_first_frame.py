from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2


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
    parser = argparse.ArgumentParser(description="Minimal OpenCV RTSP first-frame validation.")
    parser.add_argument("--url", help="Full RTSP URL. Defaults to CAMERA1/CAMERA env values.")
    parser.add_argument("--path", help="Override RTSP path, e.g. /tcp/av0_1")
    parser.add_argument("--port", type=int, help="Override RTSP port")
    parser.add_argument("--read-attempts", type=int, default=120)
    parser.add_argument("--sleep-ms", type=int, default=20)
    args = parser.parse_args()

    env = load_env()
    url = args.url or build_rtsp_url(env, path=args.path, port=args.port)
    transport = "udp" if "/udp/" in url.lower() else "tcp"
    previous_options = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        f"rtsp_transport;{transport}|stimeout;5000000|max_delay;0|fflags;nobuffer|flags;low_delay"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUT_DIR / "opencv_first_frame.jpg"
    started = time.perf_counter()
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    opened = bool(cap.isOpened())
    read_count = 0
    saved = None
    shape = None
    error = None

    try:
        if opened:
            with contextlib.suppress(Exception):
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            for _ in range(args.read_attempts):
                ok, frame = cap.read()
                read_count += 1
                if ok and frame is not None:
                    shape = list(frame.shape)
                    cv2.imwrite(str(output_path), frame)
                    saved = str(output_path)
                    break
                time.sleep(args.sleep_ms / 1000.0)
        else:
            error = "VideoCapture not opened"
    except Exception as exc:  # noqa: BLE001
        error = f"{exc.__class__.__name__}: {exc}"
    finally:
        cap.release()
        if previous_options is None:
            os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
        else:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous_options

    payload = {
        "ok": saved is not None,
        "url": mask_url(url),
        "transport": transport,
        "opened": opened,
        "read_count": read_count,
        "first_frame_saved": saved is not None,
        "latest_frame_written": saved is not None,
        "shape": shape,
        "saved": saved,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "error": error,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    import contextlib

    raise SystemExit(main())
