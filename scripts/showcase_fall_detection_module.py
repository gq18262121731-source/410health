from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.config import get_settings
from backend.services.fall_event_state_machine import FallEventStateMachine
from backend.services.fall_frame_test_service import FallFrameTestService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Showcase the core fall-detection module pipeline.")
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=ROOT / "data" / "fall_media_demo" / "inputs" / "fall_demo_01_input.mp4",
        help="Local image or video used for the showcase.",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO detector image size.")
    parser.add_argument("--posture-imgsz", type=int, default=384, help="Posture classifier image size.")
    parser.add_argument("--max-frames", type=int, default=190, help="Maximum video frames for a short showcase.")
    return parser.parse_args()


def compact_result(result: dict) -> dict:
    return {
        "raw_status": result.get("raw_status", result.get("status")),
        "event_state": result.get("event_state", result.get("status")),
        "status": result.get("status"),
        "fall_score": result.get("fall_score"),
        "scores": result.get("scores"),
        "alarm": result.get("alarm"),
        "detections": [
            {
                "bbox": item.get("bbox"),
                "label": item.get("label"),
                "confidence": item.get("confidence"),
                "posture_label": item.get("posture_label"),
                "posture_score": item.get("posture_score"),
            }
            for item in result.get("detections", [])[:3]
        ],
    }


def show_image(service: FallFrameTestService, source: Path, args: argparse.Namespace) -> None:
    frame = cv2.imread(str(source))
    if frame is None:
        raise RuntimeError(f"Could not read image: {source}")
    result = service.detect_frame(
        frame,
        include_annotated_image=False,
        imgsz=args.imgsz,
        posture_imgsz=args.posture_imgsz,
    )
    print(json.dumps(compact_result(result), ensure_ascii=False, indent=2))


def show_video(service: FallFrameTestService, source: Path, args: argparse.Namespace) -> None:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if args.max_frames > 0:
        total = min(total, args.max_frames) if total > 0 else args.max_frames

    smoother = FallEventStateMachine()
    counts: dict[str, int] = {}
    first_fall: dict | None = None
    max_score = 0.0

    with tqdm(total=total if total > 0 else None, unit="frame", desc="showcase-fall", ascii=True) as bar:
        frame_index = 0
        while True:
            if args.max_frames > 0 and frame_index >= args.max_frames:
                break
            ok, frame = capture.read()
            if not ok:
                break

            raw = service.detect_frame(
                frame,
                include_annotated_image=False,
                imgsz=args.imgsz,
                posture_imgsz=args.posture_imgsz,
            )
            result = smoother.apply(raw, frame_index=frame_index, time_s=frame_index / fps, fps=fps)
            status = str(result.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
            max_score = max(max_score, float(result.get("fall_score") or 0.0))
            if first_fall is None and status == "fall":
                first_fall = {
                    "frame": frame_index,
                    "time_s": round(frame_index / fps, 3),
                    "fall_score": round(float(result.get("fall_score") or 0.0), 4),
                    "event_state": result.get("event_state"),
                    "alarm": result.get("alarm"),
                }
            frame_index += 1
            bar.update(1)

    capture.release()
    print(
        json.dumps(
            {
                "source": str(source),
                "frames_checked": sum(counts.values()),
                "status_counts": counts,
                "max_fall_score": round(max_score, 4),
                "first_fall": first_fall,
                "state_machine": smoother.as_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    print("=== 跌倒检测模块技能展示 ===")
    print("1. 加载 YOLO 跌倒目标检测模型与姿态分类模型")
    service = FallFrameTestService(get_settings())
    warmup = service.warmup(imgsz=args.imgsz, posture_imgsz=args.posture_imgsz)
    print(json.dumps(warmup, ensure_ascii=False, indent=2))
    if not warmup.get("ok"):
        return 2

    print("2. 执行单帧模型推理，并将逐帧结果交给时序状态机")
    if source.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        show_image(service, source, args)
    else:
        show_video(service, source, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
