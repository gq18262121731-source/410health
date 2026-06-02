from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = r"C:\Users\13010\anaconda3\envs\torchgpu\python.exe"


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Vision Service for the current LAN camera.")
    parser.add_argument("--host", default="192.168.8.253")
    parser.add_argument("--password", default="410410410")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--rtsp-port", type=int, default=10554)
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--python", default=DEFAULT_PYTHON)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    python_exe = Path(args.python)
    if not python_exe.exists():
        print(f"python not found: {python_exe}", file=sys.stderr)
        return 2

    yolo_config_dir = ROOT / "Ultralytics"
    yolo_config_dir.mkdir(parents=True, exist_ok=True)

    main_url = _rtsp_url(args.username, args.password, args.host, args.rtsp_port, "/tcp/av0_0")
    analysis_url = _rtsp_url(args.username, args.password, args.host, args.rtsp_port, "/tcp/av0_1")

    env = os.environ.copy()
    env.update(
        {
            "YOLO_CONFIG_DIR": str(yolo_config_dir),
            "ENABLE_DUAL_STREAM": "true",
            "MOCK_CAMERA_ENABLED": "false",
            "DEFAULT_RTSP_URL": analysis_url,
            "MAIN_STREAM_URL": main_url,
            "ANALYSIS_STREAM_URL": analysis_url,
            "CAPTURE_BACKEND": "subprocess_opencv",
            "MAIN_CAPTURE_BACKEND": "subprocess_opencv",
            "ANALYSIS_CAPTURE_BACKEND": "subprocess_opencv",
            "CAPTURE_PROCESS_FRAME_TIMEOUT_MS": "2000",
            "CAPTURE_PROCESS_RESTART_MS": "500",
            "CAPTURE_JPEG_QUALITY": "60",
            "CAPTURE_PROCESS_OUTPUT_HEIGHT": "720",
            "CAPTURE_PROCESS_WRITE_FPS": "10",
            "MAIN_CAPTURE_JPEG_QUALITY": "55",
            "MAIN_CAPTURE_PROCESS_OUTPUT_HEIGHT": "720",
            "MAIN_CAPTURE_PROCESS_WRITE_FPS": "8",
            "CAPTURE_PROCESS_MAX_RESTARTS": "0",
            "ENABLE_TRACKING": "true",
            "YOLO_DEVICE": "cuda:0",
            "YOLO_IMGSZ": "512",
            "DETECTION_INTERVAL_MS": "125",
            "ENABLE_POSE": "true",
            "POSE_PROVIDER": "yolo",
            "POSE_WORKER_FPS": "3",
            "POSE_FPS": "3",
            "YOLO_POSE_MODEL_PATH": "yolov8n-pose.pt",
            "YOLO_POSE_CONFIDENCE": "0.25",
            "YOLO_POSE_IMGSZ": "320",
            "YOLO_POSE_DEVICE": "cuda:0",
            "POSE_SKIP_WHEN_INFERENCE_BUSY": "true",
            "POSE_MAX_INFERENCE_MS": "1500",
            "POSE_TARGET_ONLY": "false",
            "POSE_FALLBACK_TO_LARGEST_TRACK": "true",
            "POSE_FALLBACK_TO_DETECTION": "true",
            "POSE_FALLBACK_MIN_CONFIDENCE": "0.35",
            "POSE_RESULT_TTL_MS": "3000",
            "TRACKING_WORKER_FPS": "12",
            "RESULT_PUBLISH_FPS": "10",
        }
    )

    print(f"[start] camera host={args.host} rtsp_port={args.rtsp_port}")
    print(f"[start] main={_mask(main_url)}")
    print(f"[start] analysis={_mask(analysis_url)}")
    print(f"[start] YOLO_CONFIG_DIR={yolo_config_dir}")

    process = subprocess.Popen(
        [
            str(python_exe),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            args.api_host,
            "--port",
            str(args.api_port),
        ],
        cwd=str(ROOT),
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    if args.no_wait:
        print(f"[started] pid={process.pid}")
        return 0

    ready = _wait_http(f"http://{args.api_host}:{args.api_port}/healthz", 60)
    print(f"[ready] {ready} pid={process.pid}")
    print(f"[url] http://{args.api_host}:{args.api_port}/demo")
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return 0


def _rtsp_url(username: str, password: str, host: str, port: int, path: str) -> str:
    return f"rtsp://{username}:{password}@{host}:{port}{path}"


def _mask(url: str) -> str:
    prefix, rest = url.split("://", 1)
    user, after_user = rest.split(":", 1)
    _, after_password = after_user.split("@", 1)
    return f"{prefix}://{user}:***@{after_password}"


def _wait_http(url: str, timeout_sec: float) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1.5) as response:
                return 200 <= response.status < 500
        except URLError:
            time.sleep(0.5)
        except Exception:
            time.sleep(0.5)
    return False


if __name__ == "__main__":
    raise SystemExit(main())
