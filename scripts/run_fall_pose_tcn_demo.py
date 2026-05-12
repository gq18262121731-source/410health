from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from tqdm import tqdm
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.fall_pose_sequence_service import FallPoseSequenceService
from scripts.export_fall_pose_dataset import best_person_feature


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run YOLO Pose + TCN fall sequence demo on a video.")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--pose-model", type=Path, default=Path(r"D:\Program\model\fall_detection\yolo11n-pose.pt"))
    parser.add_argument("--tcn-weights", type=Path, default=Path(r"D:\Program\model\fall_detection\weights\pose_tcn_fall_v2.pt"))
    parser.add_argument("--sequence-length", type=int, default=32)
    parser.add_argument("--imgsz", type=int, default=384)
    parser.add_argument("--conf", type=float, default=0.2)
    parser.add_argument("--max-frames", type=int, default=0)
    return parser.parse_args()


def default_output_path(source: Path) -> Path:
    output_dir = ROOT / "data" / "fall_media_demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{source.stem}_pose_tcn.mp4"


def add_motion(feature: np.ndarray, previous: np.ndarray | None) -> np.ndarray:
    current = feature.reshape(17, 5).copy()
    if previous is not None:
        prev = previous.reshape(17, 5)
        current[:, 3:5] = current[:, :2] - prev[:, :2]
    else:
        current[:, 3:5] = 0.0
    return current.reshape(-1).astype(np.float32)


def draw_label(frame, text: str, color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.6
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = 14, 34
    cv2.rectangle(frame, (x, y - th - baseline - 8), (x + tw + 8, y + baseline + 4), color, -1)
    cv2.putText(frame, text, (x + 4, y - 4), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if not args.pose_model.exists():
        raise FileNotFoundError(args.pose_model)
    if not args.tcn_weights.exists():
        raise FileNotFoundError(args.tcn_weights)

    output = (args.output or default_output_path(source)).expanduser().resolve()
    json_output = (args.json or output.with_suffix(output.suffix + ".json")).expanduser().resolve()
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if args.max_frames > 0:
        total_frames = min(total_frames, args.max_frames) if total_frames > 0 else args.max_frames
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not write video: {output}")

    pose_model = YOLO(str(args.pose_model))
    device: str | int = 0 if torch.cuda.is_available() else "cpu"
    sequence_service = FallPoseSequenceService(weights_path=args.tcn_weights, sequence_length=args.sequence_length)
    records: list[dict[str, Any]] = []
    previous_feature: np.ndarray | None = None
    frame_index = 0
    started = time.perf_counter()
    with tqdm(total=total_frames if total_frames > 0 else None, unit="frame", desc="pose-tcn") as bar:
        while True:
            if args.max_frames > 0 and frame_index >= args.max_frames:
                break
            ok, frame = capture.read()
            if not ok:
                break
            with torch.inference_mode():
                pose_result = pose_model.predict(frame, verbose=False, imgsz=args.imgsz, conf=args.conf, device=device)[0]
            base_feature = best_person_feature(pose_result, width=width, height=height)
            feature = add_motion(base_feature, previous_feature)
            previous_feature = base_feature
            prediction = sequence_service.push_frame(feature, session_id=source.stem)
            probability = float(prediction.get("fall_probability") or 0.0)
            status = str(prediction.get("status") or "warming")
            color = (40, 40, 230) if status == "fall" else (0, 152, 180) if status == "suspected" else (42, 160, 80)
            draw_label(frame, f"pose_tcn={status}  prob={probability:.3f}", color)
            records.append(
                {
                    "frame": frame_index,
                    "time_s": round(frame_index / fps, 3),
                    "ready": bool(prediction.get("ready")),
                    "status": status,
                    "fall_probability": round(probability, 4),
                }
            )
            writer.write(frame)
            frame_index += 1
            bar.update(1)

    capture.release()
    writer.release()
    status_counts: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "video",
        "source": str(source),
        "output": str(output),
        "frames": frame_index,
        "fps": fps,
        "status_counts": status_counts,
        "max_fall_probability": max((float(item["fall_probability"]) for item in records), default=0.0),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "pose_model": str(args.pose_model),
        "tcn_model": sequence_service.status(),
        "records": records,
    }
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[pose-tcn] done: {output}")
    print(f"[pose-tcn] summary: {json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
