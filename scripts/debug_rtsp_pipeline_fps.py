from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_settings
from backend.services.target_pose_service import TargetPoseService
from backend.services.target_user_fall_service import TargetUserFallService
from backend.services.target_user_service import TargetUserService


def _build_rtsp_url(path: str | None = None) -> str:
    settings = get_settings()
    rtsp_path = (path or settings.camera_stream_rtsp_path).strip()
    if not rtsp_path.startswith("/"):
        rtsp_path = f"/{rtsp_path}"
    return (
        f"rtsp://{settings.camera_user}:{settings.camera_password}"
        f"@{settings.camera_ip}:{settings.camera_rtsp_port}{rtsp_path}"
    )


def _mask_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    prefix, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" not in creds:
        return url
    user, _password = creds.split(":", 1)
    return f"{prefix}://{user}:***@{host}"


def _encode_jpeg(frame) -> bytes:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
    if not ok:
        raise RuntimeError("JPEG_ENCODE_FAILED")
    return encoded.tobytes()


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure RTSP capture/processing FPS.")
    parser.add_argument("--path", default=None, help="Override RTSP path, e.g. /tcp/av0_1")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--mode", choices=["relay", "analyze"], default="relay")
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--sleep-ms", type=int, default=0)
    args = parser.parse_args()

    settings = get_settings()
    url = _build_rtsp_url(args.path)
    transport = "udp" if "/udp/" in url.lower() else "tcp"
    previous_options = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        f"rtsp_transport;{transport}|stimeout;5000000|max_delay;0|fflags;nobuffer|flags;low_delay"
    )

    pose_service = None
    fall_service = None
    if args.mode == "analyze":
        model_root = Path(settings.fall_detection_model_root)
        target_user_service = TargetUserService(
            data_root=settings.data_dir,
            model_root=model_root,
        )
        pose_service = TargetPoseService(
            model_root=model_root,
            model_path=model_root / "yolo11n-pose.pt",
        )
        fall_service = TargetUserFallService(
            data_root=settings.data_dir,
            model_root=model_root,
            target_user_service=target_user_service,
        )

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    opened = bool(cap.isOpened())
    capture_count = 0
    processed_count = 0
    first_frame_shape = None
    pose_ok_count = 0
    fall_ok_count = 0
    elapsed_capture_ms = 0.0
    elapsed_process_ms = 0.0
    started = time.perf_counter()

    try:
        if not opened:
            payload = {
                "ok": False,
                "mode": args.mode,
                "url": _mask_url(url),
                "transport": transport,
                "opened": False,
                "error": "VideoCapture not opened",
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 1

        with contextlib.suppress(Exception):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        deadline = time.perf_counter() + args.seconds
        while time.perf_counter() < deadline:
            t0 = time.perf_counter()
            ok, frame = cap.read()
            elapsed_capture_ms += (time.perf_counter() - t0) * 1000
            if not ok or frame is None:
                continue
            capture_count += 1
            if first_frame_shape is None:
                first_frame_shape = list(frame.shape)

            t1 = time.perf_counter()
            if args.mode == "relay":
                _encode_jpeg(frame)
                processed_count += 1
            else:
                assert pose_service is not None and fall_service is not None
                pose_result = pose_service.estimate_pose(
                    frame,
                    imgsz=args.imgsz,
                    conf=0.2,
                    session_id="rtsp-fps-debug",
                )
                pose_ok_count += 1 if pose_result.get("ok") else 0
                ok2, buffer = cv2.imencode(".jpg", frame)
                if ok2:
                    fall_result = fall_service.detect(
                        buffer.tobytes(),
                        include_annotated_image=False,
                        target_only=False,
                        session_id="rtsp-fps-debug",
                    )
                    fall_ok_count += 1 if fall_result.get("ok") else 0
                processed_count += 1
            elapsed_process_ms += (time.perf_counter() - t1) * 1000

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)
    finally:
        cap.release()
        if previous_options is None:
            os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
        else:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous_options

    total_elapsed = max(time.perf_counter() - started, 0.001)
    payload = {
        "ok": True,
        "mode": args.mode,
        "url": _mask_url(url),
        "transport": transport,
        "opened": True,
        "frame_shape": first_frame_shape,
        "capture_count": capture_count,
        "processed_count": processed_count,
        "capture_fps": round(capture_count / total_elapsed, 2),
        "processed_fps": round(processed_count / total_elapsed, 2),
        "avg_capture_ms": round(elapsed_capture_ms / capture_count, 2) if capture_count else None,
        "avg_process_ms": round(elapsed_process_ms / processed_count, 2) if processed_count else None,
        "pose_ok_count": pose_ok_count if args.mode == "analyze" else None,
        "fall_ok_count": fall_ok_count if args.mode == "analyze" else None,
        "elapsed_s": round(total_elapsed, 2),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import contextlib

    raise SystemExit(main())
