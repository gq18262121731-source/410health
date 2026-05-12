from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_settings
from backend.services.fall_event_state_machine import FallEventStateMachine, FallEventStateMachineConfig
from backend.services.fall_frame_test_service import FallFrameTestService
from run_fall_media_demo import draw_result, save_review_frame, should_save_review_frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact fall video demo for live code explanation.")
    parser.add_argument("source", type=Path, help="Local video path.")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Annotated output video path.")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--posture-imgsz", type=int, default=384)
    parser.add_argument("--process-every", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--save-review-frames", action="store_true")
    return parser.parse_args()


def output_path(source: Path) -> Path:
    output_dir = ROOT / "data" / "fall_media_demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{source.stem}_showcase_detected.mp4"


def build_smoother() -> FallEventStateMachine:
    return FallEventStateMachine(
        FallEventStateMachineConfig(
            window_frames=9,
            fall_confirm_frames=3,
            fall_hold_frames=12,
            fall_score_threshold=0.72,
            suspected_score_threshold=0.42,
        )
    )


def add_count(bucket: dict[str, int], value: str) -> None:
    bucket[value] = bucket.get(value, 0) + 1


def smooth_result(
    smoother: FallEventStateMachine,
    result: dict[str, Any],
    frame_index: int,
    fps: float,
) -> dict[str, Any]:
    return smoother.apply(result, frame_index=frame_index, time_s=frame_index / fps, fps=fps)


def extract_states(result: dict[str, Any], raw_result: dict[str, Any]) -> tuple[str, str, str, str]:
    raw_status = str(result.get("raw_status") or raw_result.get("status") or "unknown")
    status = str(result.get("status") or "unknown")
    event_state = str(result.get("event_state") or status)
    alarm = result.get("alarm") if isinstance(result.get("alarm"), dict) else {}
    return raw_status, status, event_state, str(alarm.get("level") or "normal")


def make_record(frame_index: int, fps: float, result: dict[str, Any], states: tuple[str, str, str, str]) -> dict[str, Any]:
    raw_status, status, event_state, alarm_level = states
    return {
        "frame": frame_index,
        "time_s": round(frame_index / fps, 3),
        "raw_status": raw_status,
        "status": status,
        "event_state": event_state,
        "alarm_level": alarm_level,
        "fall_score": round(float(result.get("fall_score") or 0.0), 4),
    }


def append_review_frame(
    review_frames: list[dict[str, Any]],
    frame,
    review_dir: Path,
    frame_index: int,
    fps: float,
    result: dict[str, Any],
    states: tuple[str, str, str, str],
) -> None:
    if not should_save_review_frame(result, frame_index):
        return
    raw_status, status, event_state, alarm_level = states
    review_frames.append(
        {
            "frame": frame_index,
            "time_s": round(frame_index / fps, 3),
            "path": save_review_frame(frame, review_dir, frame_index, result),
            "raw_status": raw_status,
            "status": status,
            "event_state": event_state,
            "alarm_level": alarm_level,
            "fall_score": round(float(result.get("fall_score") or 0.0), 4),
        }
    )


def run_video(service: FallFrameTestService, source: Path, output: Path, args: argparse.Namespace) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if args.max_frames > 0 and total_frames > 0:
        total_frames = min(total_frames, args.max_frames)

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if width <= 0 or height <= 0 or not writer.isOpened():
        raise RuntimeError(f"Invalid video or output path: {source}")

    smoother = build_smoother()
    review_dir = ROOT / "data" / "fall_media_demo" / "review_frames" / source.stem
    frame_records: list[dict[str, Any]] = []
    review_frames: list[dict[str, Any]] = []
    raw_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    alarm_counts: dict[str, int] = {}
    last_result: dict[str, Any] = {"status": "warming", "fall_score": 0.0, "detections": []}
    frame_index = processed = 0
    max_score = 0.0
    started = time.perf_counter()
    progress_total = total_frames if total_frames > 0 else None

    with tqdm(total=progress_total, unit="frame", desc="fall-detect") as bar:
        while True:
            if args.max_frames > 0 and frame_index >= args.max_frames:
                break
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % max(1, args.process_every) == 0:
                last_result = service.detect_frame(
                    frame,
                    include_annotated_image=False,
                    imgsz=args.imgsz,
                    posture_imgsz=args.posture_imgsz,
                )
                processed += 1
                max_score = max(max_score, float(last_result.get("fall_score") or 0.0))
            display_result = smooth_result(smoother, last_result, frame_index, fps)
            states = extract_states(display_result, last_result)
            for bucket, value in zip((raw_counts, status_counts, event_counts, alarm_counts), states):
                add_count(bucket, value)
            frame_records.append(make_record(frame_index, fps, display_result, states))
            draw_result(frame, display_result)
            if args.save_review_frames:
                append_review_frame(review_frames, frame, review_dir, frame_index, fps, display_result, states)
            writer.write(frame)
            frame_index += 1
            bar.update(1)

    capture.release()
    writer.release()
    return {
        "source": str(source),
        "output": str(output),
        "frames": frame_index,
        "processed_frames": processed,
        "fps": fps,
        "max_fall_score": round(max_score, 4),
        "status_counts": status_counts,
        "raw_status_counts": raw_counts,
        "event_state_counts": event_counts,
        "alarm_counts": alarm_counts,
        "review_frame_count": len(review_frames),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "frame_records": frame_records,
        "review_frames": review_frames[:100],
    }


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    output = (args.output or output_path(source)).expanduser().resolve()
    json_output = output.with_suffix(output.suffix + ".json")

    print(f"[fall-showcase] source: {source}")
    print(f"[fall-showcase] output: {output}")
    service = FallFrameTestService(get_settings())
    warmup = service.warmup(imgsz=args.imgsz, posture_imgsz=args.posture_imgsz)
    print(f"[fall-showcase] warmup: {json.dumps(warmup, ensure_ascii=False)}")
    if not warmup.get("ok"):
        return 2

    summary = run_video(service, source, output, args)
    payload = {"generated_at": datetime.now().isoformat(timespec="seconds"), "model": service.status(), **summary}
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fall-showcase] done: {output}")
    print(f"[fall-showcase] summary: {json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
