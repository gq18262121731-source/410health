from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.behavior.model_classifier import BEHAVIOR_LABELS, COCO_KEYPOINT_NAMES, PoseFeatureBuilder

DEFAULT_OUTPUT_DIR = ROOT / "datasets" / "behavior_samples"
DEFAULT_JSONL = DEFAULT_OUTPUT_DIR / "samples.jsonl"
DEFAULT_CSV = DEFAULT_OUTPUT_DIR / "features.csv"


def configure_environment(args: argparse.Namespace) -> None:
    os.environ.setdefault("DETECTION_ENABLED", "true")
    os.environ.setdefault("ENABLE_TRACKING", "true")
    os.environ.setdefault("ENABLE_POSE", "true")
    os.environ.setdefault("POSE_PROVIDER", "yolo")
    os.environ.setdefault("YOLO_CONFIDENCE", str(args.yolo_confidence))
    os.environ.setdefault("YOLO_IMGSZ", str(args.yolo_imgsz))
    os.environ.setdefault("YOLO_POSE_CONFIDENCE", str(args.pose_confidence))
    os.environ.setdefault("YOLO_POSE_IMGSZ", str(args.pose_imgsz))
    os.environ.setdefault("POSE_SKIP_WHEN_INFERENCE_BUSY", "false")
    os.environ.setdefault("POSE_FPS", "1000")


def load_runtime_components() -> tuple[Any, Any, Any, Any]:
    from app.core.config import get_settings
    from app.detection.object_detector import YoloPersonDetector
    from app.services.pose_service import PoseService
    from app.services.tracking_service import TrackingService

    settings = get_settings()
    return (
        settings,
        YoloPersonDetector(settings),
        TrackingService(settings),
        PoseService(settings),
    )


def collect_samples(args: argparse.Namespace) -> dict[str, Any]:
    require_video_deps()
    import cv2

    configure_environment(args)
    settings, detector, tracking, pose = load_runtime_components()
    source = resolve_source(args.source)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"could not open source: {args.source}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    camera_id = args.camera_id
    feature_builder = PoseFeatureBuilder(motion_window_size=args.motion_window)

    jsonl_path = Path(args.jsonl)
    csv_path = Path(args.csv)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    label = args.label
    written = 0
    processed_frames = 0
    read_frames = 0
    started_at = time.perf_counter()
    first_csv_write = not csv_path.exists() or csv_path.stat().st_size == 0

    with jsonl_path.open("a", encoding="utf-8") as jsonl_file, csv_path.open("a", newline="", encoding="utf-8") as csv_file:
        csv_writer = None

        frame_index = 0
        while args.max_frames <= 0 or frame_index < args.max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            read_frames += 1

            if frame_index % args.frame_stride != 0:
                frame_index += 1
                continue

            timestamp_sec = frame_index / fps if fps > 0 else time.perf_counter() - started_at
            objects = detector.detect(frame)
            objects = tracking.enrich(camera_id, objects, frame=frame)
            objects = pose.enrich(camera_id, frame, objects)
            candidates = select_sample_objects(objects, args.max_persons_per_frame)

            for person_index, obj in enumerate(candidates):
                if not obj.pose:
                    continue
                record = object_to_sample_record(
                    obj,
                    label=label,
                    source=args.source,
                    camera_id=camera_id,
                    frame_index=frame_index,
                    timestamp_sec=timestamp_sec,
                    fps=fps,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    person_index=person_index,
                    settings=settings,
                )
                features = feature_builder.extract(record)
                jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")

                row = {
                    "label": label,
                    "source": args.source,
                    "frame_index": frame_index,
                    "track_id": record.get("track_id"),
                    **features,
                }
                if csv_writer is None:
                    csv_writer = csv.DictWriter(csv_file, fieldnames=list(row.keys()))
                    if first_csv_write:
                        csv_writer.writeheader()
                csv_writer.writerow(row)
                written += 1

            processed_frames += 1
            if args.preview:
                draw_preview(frame, candidates, label)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if args.limit_samples > 0 and written >= args.limit_samples:
                break
            frame_index += 1

    cap.release()
    if args.preview:
        cv2.destroyAllWindows()

    return {
        "source": args.source,
        "label": label,
        "jsonl": str(jsonl_path),
        "csv": str(csv_path),
        "read_frames": read_frames,
        "processed_frames": processed_frames,
        "written_samples": written,
        "elapsed_sec": round(time.perf_counter() - started_at, 2),
    }


def object_to_sample_record(
    obj: Any,
    *,
    label: str,
    source: str,
    camera_id: str,
    frame_index: int,
    timestamp_sec: float,
    fps: float,
    frame_width: int,
    frame_height: int,
    person_index: int,
    settings: Any,
) -> dict[str, Any]:
    pose = obj.pose or {}
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "camera_id": camera_id,
        "label": label,
        "frame_index": frame_index,
        "timestamp_sec": timestamp_sec,
        "fps": fps,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "person_index": person_index,
        "track_id": obj.track_id,
        "bbox": obj.bbox,
        "detection_confidence": obj.confidence,
        "is_target": obj.is_target,
        "pose_provider": settings.pose_provider,
        "pose_model": settings.yolo_pose_model_path,
        "keypoints": pose.get("keypoints") if isinstance(pose, dict) else [],
        "skeleton_confidence": pose.get("skeleton_confidence") if isinstance(pose, dict) else None,
    }


def select_sample_objects(objects: list[Any], max_persons: int) -> list[Any]:
    candidates = [item for item in objects if item.pose and item.track_id is not None]
    if not candidates:
        candidates = [item for item in objects if item.pose]
    candidates.sort(key=area, reverse=True)
    return candidates[: max(1, max_persons)]


def draw_preview(frame: Any, objects: list[Any], label: str) -> None:
    import cv2

    for obj in objects:
        x1, y1, x2, y2 = [int(value) for value in obj.bbox]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (45, 220, 90), 2)
        pose = obj.pose or {}
        keypoints = {
            item.get("name"): item
            for item in pose.get("keypoints", [])
            if item.get("confidence", 0) >= 0.2
        }
        for name in COCO_KEYPOINT_NAMES:
            kp = keypoints.get(name)
            if kp:
                cv2.circle(frame, (int(kp["x"]), int(kp["y"])), 3, (255, 255, 255), -1)
        cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (45, 220, 90), 2)
    cv2.imshow("behavior sample collector", frame)


def area(obj: Any) -> float:
    x1, y1, x2, y2 = obj.bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def resolve_source(source: str) -> str | int:
    if source.isdigit():
        return int(source)
    return source


def require_video_deps() -> None:
    missing = []
    for module_name in ("cv2", "ultralytics"):
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        raise RuntimeError(
            "missing runtime dependency for collection: "
            + ", ".join(missing)
            + ". Install project video/YOLO dependencies before collecting samples."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect YOLO-Pose behavior samples as a side-channel PoC dataset.")
    parser.add_argument("--source", required=True, help="RTSP URL, local video path, or webcam index.")
    parser.add_argument("--label", required=True, choices=BEHAVIOR_LABELS)
    parser.add_argument("--jsonl", default=str(DEFAULT_JSONL))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--camera-id", default="behavior_poc")
    parser.add_argument("--frame-stride", type=int, default=5)
    parser.add_argument("--max-frames", type=int, default=0, help="0 means until source ends.")
    parser.add_argument("--limit-samples", type=int, default=0, help="0 means no sample limit.")
    parser.add_argument("--max-persons-per-frame", type=int, default=1)
    parser.add_argument("--motion-window", type=int, default=8)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--yolo-confidence", type=float, default=0.35)
    parser.add_argument("--yolo-imgsz", type=int, default=640)
    parser.add_argument("--pose-confidence", type=float, default=0.25)
    parser.add_argument("--pose-imgsz", type=int, default=320)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = collect_samples(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
