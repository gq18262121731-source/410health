from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "Ultralytics"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_settings
from backend.services.target_pose_service import COCO_SKELETON, TargetPoseService
from backend.services.target_user_fall_service import TargetUserFallService
from backend.services.target_user_service import TargetUserService


def _draw_pose_overlay(frame: np.ndarray, pose_payload: dict[str, Any]) -> np.ndarray:
    canvas = frame.copy()
    pose = pose_payload.get("pose") if isinstance(pose_payload, dict) else None
    if not isinstance(pose, dict):
        return canvas
    points = pose.get("points")
    if not isinstance(points, list):
        return canvas

    parsed_points: dict[int, tuple[int, int, float]] = {}
    for point in points:
        if not isinstance(point, dict):
            continue
        idx = int(point.get("index", -1))
        x = int(float(point.get("x", 0)))
        y = int(float(point.get("y", 0)))
        score = float(point.get("score", 0.0))
        parsed_points[idx] = (x, y, score)

    for item in COCO_SKELETON:
        a = int(item["from"])
        b = int(item["to"])
        pa = parsed_points.get(a)
        pb = parsed_points.get(b)
        if pa is None or pb is None:
            continue
        if pa[2] < 0.2 or pb[2] < 0.2:
            continue
        cv2.line(canvas, (pa[0], pa[1]), (pb[0], pb[1]), (0, 220, 180), 2, cv2.LINE_AA)

    for idx, (x, y, score) in parsed_points.items():
        if score < 0.2:
            continue
        cv2.circle(canvas, (x, y), 4, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(canvas, (x, y), 8, (0, 220, 180), 1, cv2.LINE_AA)
        cv2.putText(
            canvas,
            str(idx),
            (x + 6, y - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    posture = pose.get("posture") if isinstance(pose.get("posture"), dict) else {}
    label = str(posture.get("label") or "unknown")
    conf = float(posture.get("confidence") or posture.get("score") or 0.0)
    cv2.putText(
        canvas,
        f"pose={label} conf={conf:.2f}",
        (16, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 220, 180),
        2,
        cv2.LINE_AA,
    )
    return canvas


def _load_camera_frame(camera_index: int) -> np.ndarray:
    cap = cv2.VideoCapture(camera_index, cv2.CAP_ANY)
    if not cap.isOpened():
        raise RuntimeError(f"LOCAL_CAMERA_OPEN_FAILED index={camera_index}")
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError("LOCAL_CAMERA_FRAME_READ_FAILED")
        return frame
    finally:
        cap.release()


def _load_video_frame(video_path: Path, frame_index: int) -> np.ndarray:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"VIDEO_OPEN_FAILED path={video_path}")
    try:
        if frame_index > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError("VIDEO_FRAME_READ_FAILED")
        return frame
    finally:
        cap.release()


def _load_image_frame(image_path: Path) -> np.ndarray:
    frame = cv2.imread(str(image_path))
    if frame is None:
        raise RuntimeError(f"IMAGE_READ_FAILED path={image_path}")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal camera -> pose -> fall debug pipeline.")
    parser.add_argument("--camera-index", type=int, default=0, help="Local camera index for cv2 capture.")
    parser.add_argument("--video-path", type=Path, help="Optional video path instead of local camera.")
    parser.add_argument("--image-path", type=Path, help="Optional image path instead of local camera/video.")
    parser.add_argument("--frame-index", type=int, default=0, help="Frame index when using --video-path.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "tmp_debug_camera_pipeline")
    parser.add_argument("--imgsz", type=int, default=320)
    args = parser.parse_args()

    settings = get_settings()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.image_path:
        frame = _load_image_frame(args.image_path)
        source = {"kind": "image", "path": str(args.image_path)}
    elif args.video_path:
        frame = _load_video_frame(args.video_path, args.frame_index)
        source = {"kind": "video", "path": str(args.video_path), "frame_index": args.frame_index}
    else:
        frame = _load_camera_frame(args.camera_index)
        source = {"kind": "camera", "camera_index": args.camera_index}

    frame_path = output_dir / "frame.jpg"
    cv2.imwrite(str(frame_path), frame)

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

    pose_started = time.perf_counter()
    pose_result = pose_service.estimate_pose(
        frame,
        imgsz=args.imgsz,
        conf=0.2,
        session_id="debug-pipeline",
    )
    pose_elapsed_ms = round((time.perf_counter() - pose_started) * 1000, 1)
    pose_overlay = _draw_pose_overlay(frame, pose_result)
    pose_result_path = output_dir / "pose_result.jpg"
    cv2.imwrite(str(pose_result_path), pose_overlay)

    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("JPEG_ENCODE_FAILED")

    fall_started = time.perf_counter()
    fall_result = fall_service.detect(
        buffer.tobytes(),
        include_annotated_image=False,
        target_only=False,
        session_id="debug-pipeline",
    )
    fall_elapsed_ms = round((time.perf_counter() - fall_started) * 1000, 1)

    points = ((pose_result.get("pose") or {}).get("points") or []) if isinstance(pose_result, dict) else []
    visible_points = sum(1 for point in points if isinstance(point, dict) and float(point.get("score") or 0.0) >= 0.2)
    posture = ((pose_result.get("pose") or {}).get("posture") or {}) if isinstance(pose_result, dict) else {}
    fall_payload = fall_result.get("fall_result") if isinstance(fall_result, dict) else None
    if not isinstance(fall_payload, dict):
        fall_payload = {}

    payload = {
        "source": source,
        "frame_path": str(frame_path),
        "pose_result_path": str(pose_result_path),
        "frame_shape": list(frame.shape),
        "pose_ok": bool(pose_result.get("ok")) if isinstance(pose_result, dict) else False,
        "pose_latency_ms": pose_elapsed_ms,
        "pose_model_latency_ms": pose_result.get("latency_ms") if isinstance(pose_result, dict) else None,
        "pose_label": posture.get("label"),
        "pose_confidence": posture.get("confidence") or posture.get("score"),
        "pose_visible_points": visible_points,
        "fall_ok": bool(fall_result.get("ok")) if isinstance(fall_result, dict) else False,
        "fall_latency_ms": fall_elapsed_ms,
        "fall_status": fall_result.get("status") if isinstance(fall_result, dict) else None,
        "fall_detected": fall_payload.get("fall_detected"),
        "fall_score": fall_payload.get("fall_score"),
        "target_match": fall_result.get("target_match") if isinstance(fall_result, dict) else None,
        "tracking": fall_result.get("tracking") if isinstance(fall_result, dict) else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
