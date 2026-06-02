from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import cv2


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def configure_env() -> None:
    defaults = {
        "ENABLE_TRACKING": "true",
        "ENABLE_POSE": "true",
        "POSE_PROVIDER": "yolo",
        "ENABLE_BEHAVIOR": "true",
        "ENABLE_TEMPORAL": "true",
        "ENABLE_IDENTITY_BINDING": "false",
        "YOLO_DEVICE": "cuda:0",
        "YOLO_IMGSZ": "416",
        "DETECTION_INTERVAL_MS": "100",
        "POSE_FPS": "5",
        "POSE_WORKER_FPS": "5",
        "YOLO_POSE_IMGSZ": "320",
        "YOLO_POSE_DEVICE": "cuda:0",
        "POSE_SKIP_WHEN_INFERENCE_BUSY": "true",
        "POSE_TARGET_ONLY": "false",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5.19B local pose activation debug.")
    parser.add_argument("--video-path", default=str(ROOT / "tests" / "fixtures" / "person_bus_loop.mp4"))
    parser.add_argument("--camera-id", default="pose_debug_video")
    parser.add_argument("--max-frames", type=int, default=180)
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--output-json", default=str(ROOT / "logs" / "runtime_debug" / "phase5_19b_pose_activation_debug.json"))
    args = parser.parse_args()

    configure_env()

    from app.core.config import get_settings
    from app.detection.object_detector import YoloPersonDetector
    from app.services.behavior_service import BehaviorService
    from app.services.pose_service import PoseService
    from app.services.temporal_service import TemporalService
    from app.services.tracking_service import TrackingService

    settings = get_settings()
    detector = YoloPersonDetector(settings)
    tracking = TrackingService(settings)
    pose = PoseService(settings)
    behavior = BehaviorService(settings)
    temporal = TemporalService(settings)

    cap = cv2.VideoCapture(str(Path(args.video_path)))
    if not cap.isOpened():
        raise SystemExit(f"could not open video: {args.video_path}")

    rows: list[dict[str, Any]] = []
    try:
        frame_index = 0
        processed = 0
        while processed < args.max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % max(args.frame_stride, 1) != 0:
                frame_index += 1
                continue

            detections = detector.detect(frame)
            tracked = tracking.enrich(args.camera_id, detections, frame=frame)
            posed = pose.enrich(args.camera_id, frame, tracked)
            behaved = behavior.enrich(args.camera_id, posed)
            temporal.enrich(args.camera_id, behaved)

            pose_status = pose.status(args.camera_id)
            tracking_status = tracking.status(args.camera_id)
            posed_track_ids = [item.track_id for item in posed if item.pose is not None]
            target_track_ids = [item.track_id for item in tracked if item.is_target]
            rows.append(
                {
                    "frame_index": frame_index,
                    "detection_objects_count": len(detections),
                    "tracking_objects_count": len(tracked),
                    "target_objects_count": sum(1 for item in tracked if item.is_target),
                    "pose_objects_count": sum(1 for item in posed if item.pose is not None),
                    "posed_track_ids": posed_track_ids,
                    "target_track_ids": target_track_ids,
                    "tracking_state": tracking_status.tracking_state,
                    "tracked_target_id": tracking_status.tracked_target_id,
                    "pose_fps": pose_status.pose_fps,
                    "pose_attempts": pose_status.pose_attempts,
                    "pose_success": pose_status.pose_success,
                    "pose_skip_reasons": pose_status.pose_skip_reasons,
                    "pose_target_source": pose_status.pose_target_source,
                    "fallback_used_count": pose_status.fallback_used_count,
                    "last_fallback_reason": pose_status.last_fallback_reason,
                    "pose_status_objects_count": pose_status.pose_objects_count,
                    "pose_result_writeback_ok": pose_status.pose_result_writeback_ok,
                    "last_target_track_id": pose_status.last_target_track_id,
                    "last_target_confidence": pose_status.last_target_confidence,
                    "last_bbox": pose_status.last_bbox,
                    "last_identity_state": pose_status.last_identity_state,
                    "last_pose_error": pose_status.last_pose_error,
                    "last_pose_started_at": pose_status.last_pose_started_at,
                    "last_pose_completed_at": pose_status.last_pose_completed_at,
                    "last_inference_latency_ms": pose_status.last_inference_latency_ms,
                }
            )
            frame_index += 1
            processed += 1
    finally:
        cap.release()

    summary = rows[-1] if rows else {}
    payload = {
        "video_path": str(Path(args.video_path)),
        "camera_id": args.camera_id,
        "settings": {
            "YOLO_IMGSZ": settings.yolo_imgsz,
            "POSE_FPS": settings.pose_fps,
            "POSE_WORKER_FPS": settings.pose_worker_fps,
            "YOLO_POSE_IMGSZ": settings.yolo_pose_imgsz,
            "POSE_TARGET_ONLY": settings.pose_target_only,
        },
        "summary": summary,
        "rows": rows,
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
