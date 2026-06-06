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


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v"}
RISK_LABELS = {"fall", "fallen", "lying", "target_risk"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local fall-detection models on one image/video and save an annotated result."
    )
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=ROOT / "tmp_detect_frame.jpg",
        help="Local image or video path. Defaults to tmp_detect_frame.jpg for IDE one-click runs.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output image/video path. Defaults to data/fall_media_demo/<name>_detected.<ext>.",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO detector image size.")
    parser.add_argument("--posture-imgsz", type=int, default=384, help="Posture classifier image size.")
    parser.add_argument(
        "--process-every",
        type=int,
        default=1,
        help="For video, run model every N frames and reuse the last result for skipped frames.",
    )
    parser.add_argument("--max-frames", type=int, default=0, help="Optional video frame limit for quick demos.")
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON summary output path.")
    parser.add_argument(
        "--no-temporal-smoothing",
        action="store_true",
        help="Disable video event smoothing and show raw per-frame model statuses only.",
    )
    parser.add_argument(
        "--event-window-frames",
        type=int,
        default=9,
        help="Recent-frame window used to confirm a fall event in video mode.",
    )
    parser.add_argument(
        "--fall-confirm-frames",
        type=int,
        default=3,
        help="Minimum risky frames in the recent window required to confirm fall status.",
    )
    parser.add_argument(
        "--fall-hold-frames",
        type=int,
        default=12,
        help="Frames to hold a confirmed fall state across short raw-model dropouts.",
    )
    parser.add_argument(
        "--fall-score-threshold",
        type=float,
        default=0.72,
        help="Recent frame fall score threshold used by temporal smoothing.",
    )
    parser.add_argument(
        "--suspected-score-threshold",
        type=float,
        default=0.42,
        help="Recent frame suspected-risk score threshold used by temporal smoothing.",
    )
    parser.add_argument(
        "--save-frame-records",
        action="store_true",
        help="Save per-frame raw scores in the JSON summary for later evaluation/tuning.",
    )
    parser.add_argument(
        "--save-review-frames",
        action="store_true",
        help="Save uncertain or state-transition frames for later labeling and model improvement.",
    )
    parser.add_argument(
        "--review-frame-dir",
        type=Path,
        default=None,
        help="Directory for --save-review-frames. Defaults to data/fall_media_demo/review_frames/<video-name>.",
    )
    return parser.parse_args()


def default_output_path(source: Path) -> Path:
    output_dir = ROOT / "data" / "fall_media_demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".mp4" if source.suffix.lower() in VIDEO_SUFFIXES else source.suffix
    return output_dir / f"{source.stem}_detected{suffix}"


def clamp_box(box: list[Any], width: int, height: int) -> tuple[int, int, int, int] | None:
    if len(box) < 4:
        return None
    x1, y1, x2, y2 = [int(round(float(value))) for value in box[:4]]
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(0, min(width - 1, x2))
    y2 = max(0, min(height - 1, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def draw_result(frame, result: dict[str, Any]) -> None:
    height, width = frame.shape[:2]
    status = str(result.get("status") or "unknown")
    event_state = str(result.get("event_state") or status)
    raw_status = str(result.get("raw_status") or "")
    fall_score = float(result.get("fall_score") or 0.0)
    alarm = result.get("alarm") if isinstance(result.get("alarm"), dict) else {}
    alarm_level = str(alarm.get("level") or "normal")
    detections = result.get("detections") or []

    for item in detections:
        box = clamp_box(list(item.get("bbox") or []), width, height)
        if box is None:
            continue
        x1, y1, x2, y2 = box
        label = str(item.get("label") or "object").lower()
        confidence = float(item.get("confidence") or 0.0)
        posture_label = str(item.get("posture_label") or "").lower()
        posture_score = item.get("posture_score")
        color = (40, 40, 230) if label in RISK_LABELS or status == "fall" else (47, 125, 246)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        text = f"{label} {confidence:.2f}"
        if posture_label:
            text += f" | {posture_label}"
            if posture_score is not None:
                text += f" {float(posture_score):.2f}"
        draw_label(frame, text, x1, max(0, y1 - 8), color)

    panel_color = (40, 40, 230) if status == "fall" else (0, 152, 180) if status == "suspected" else (42, 160, 80)
    raw_text = f"  raw={raw_status}" if raw_status and raw_status != status else ""
    panel = f"event={event_state}  status={status}{raw_text}  score={fall_score:.3f}  alarm={alarm_level}"
    draw_label(frame, panel, 14, 32, panel_color)


def draw_label(frame, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    y = max(th + baseline + 4, y)
    cv2.rectangle(frame, (x, y - th - baseline - 6), (x + tw + 8, y + baseline + 2), color, -1)
    cv2.putText(frame, text, (x + 4, y - 4), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def run_image(service: FallFrameTestService, source: Path, output: Path, args: argparse.Namespace) -> dict[str, Any]:
    frame = cv2.imread(str(source))
    if frame is None:
        raise RuntimeError(f"Could not read image: {source}")
    result = service.detect_frame(
        frame,
        include_annotated_image=False,
        imgsz=args.imgsz,
        posture_imgsz=args.posture_imgsz,
    )
    draw_result(frame, result)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), frame):
        raise RuntimeError(f"Could not write image: {output}")
    return {
        "kind": "image",
        "source": str(source),
        "output": str(output),
        "frames": 1,
        "processed_frames": 1,
        "result": strip_heavy_fields(result),
    }


def summarize_timeline(frame_records: list[dict[str, Any]], *, fps: float) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for item in frame_records:
        status = str(item["status"])
        if current is None or current["status"] != status:
            if current is not None:
                segments.append(current)
            current = {
                "status": status,
                "start_frame": item["frame"],
                "end_frame": item["frame"],
                "start_s": round(float(item["frame"]) / fps, 3),
                "end_s": round(float(item["frame"]) / fps, 3),
                "max_fall_score": float(item["fall_score"]),
            }
        else:
            current["end_frame"] = item["frame"]
            current["end_s"] = round(float(item["frame"]) / fps, 3)
            current["max_fall_score"] = max(float(current["max_fall_score"]), float(item["fall_score"]))
    if current is not None:
        segments.append(current)
    for item in segments:
        item["duration_s"] = round(float(item["end_s"]) - float(item["start_s"]) + (1.0 / fps), 3)
        item["max_fall_score"] = round(float(item["max_fall_score"]), 4)
    return segments


def summarize_field_timeline(frame_records: list[dict[str, Any]], *, fps: float, field: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for item in frame_records:
        value = str(item.get(field) or "unknown")
        if current is None or current[field] != value:
            if current is not None:
                segments.append(current)
            current = {
                field: value,
                "start_frame": item["frame"],
                "end_frame": item["frame"],
                "start_s": round(float(item["frame"]) / fps, 3),
                "end_s": round(float(item["frame"]) / fps, 3),
                "max_fall_score": float(item["fall_score"]),
            }
        else:
            current["end_frame"] = item["frame"]
            current["end_s"] = round(float(item["frame"]) / fps, 3)
            current["max_fall_score"] = max(float(current["max_fall_score"]), float(item["fall_score"]))
    if current is not None:
        segments.append(current)
    for item in segments:
        item["duration_s"] = round(float(item["end_s"]) - float(item["start_s"]) + (1.0 / fps), 3)
        item["max_fall_score"] = round(float(item["max_fall_score"]), 4)
    return segments


def should_save_review_frame(display_result: dict[str, Any], frame_index: int) -> bool:
    raw_status = str(display_result.get("raw_status") or "")
    status = str(display_result.get("status") or "")
    event_state = str(display_result.get("event_state") or "")
    fall_score = float(display_result.get("fall_score") or 0.0)
    if raw_status and raw_status != status:
        return True
    if event_state in {"suspected", "falling", "recovery"} and frame_index % 5 == 0:
        return True
    return 0.36 <= fall_score <= 0.72 and frame_index % 10 == 0


def save_review_frame(frame, review_dir: Path, frame_index: int, display_result: dict[str, Any]) -> str:
    review_dir.mkdir(parents=True, exist_ok=True)
    event_state = str(display_result.get("event_state") or display_result.get("status") or "unknown")
    raw_status = str(display_result.get("raw_status") or "raw")
    fall_score = float(display_result.get("fall_score") or 0.0)
    path = review_dir / f"frame_{frame_index:06d}_{event_state}_{raw_status}_{fall_score:.3f}.jpg"
    cv2.imwrite(str(path), frame)
    return str(path)


def run_video(service: FallFrameTestService, source: Path, output: Path, args: argparse.Namespace) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if args.max_frames > 0:
        total_frames = min(total_frames, args.max_frames) if total_frames > 0 else args.max_frames
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid video dimensions: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not write video: {output}")

    frame_index = 0
    processed = 0
    max_score = 0.0
    raw_status_counts: dict[str, int] = {}
    smoothed_status_counts: dict[str, int] = {}
    event_state_counts: dict[str, int] = {}
    alarm_counts: dict[str, int] = {}
    frame_records: list[dict[str, Any]] = []
    review_frames: list[dict[str, Any]] = []
    review_dir = args.review_frame_dir
    if review_dir is None:
        review_dir = ROOT / "data" / "fall_media_demo" / "review_frames" / source.stem
    smoother = None
    if not args.no_temporal_smoothing:
        smoother = FallEventStateMachine(
            FallEventStateMachineConfig(
                window_frames=args.event_window_frames,
                fall_confirm_frames=args.fall_confirm_frames,
                fall_hold_frames=args.fall_hold_frames,
                fall_score_threshold=args.fall_score_threshold,
                suspected_score_threshold=args.suspected_score_threshold,
            )
        )
    last_result: dict[str, Any] = {
        "ok": True,
        "status": "warming",
        "fall_score": 0.0,
        "detections": [],
    }
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
            display_result = (
                smoother.apply(last_result, frame_index=frame_index, time_s=frame_index / fps, fps=fps)
                if smoother is not None
                else {**last_result, "raw_status": last_result.get("status"), "event_state": last_result.get("status")}
            )
            raw_status = str(display_result.get("raw_status") or last_result.get("status") or "unknown")
            status = str(display_result.get("status") or "unknown")
            event_state = str(display_result.get("event_state") or status)
            alarm = display_result.get("alarm") if isinstance(display_result.get("alarm"), dict) else {}
            alarm_level = str(alarm.get("level") or "normal")
            raw_status_counts[raw_status] = raw_status_counts.get(raw_status, 0) + 1
            smoothed_status_counts[status] = smoothed_status_counts.get(status, 0) + 1
            event_state_counts[event_state] = event_state_counts.get(event_state, 0) + 1
            alarm_counts[alarm_level] = alarm_counts.get(alarm_level, 0) + 1
            frame_records.append(
                {
                    "frame": frame_index,
                    "time_s": round(frame_index / fps, 3),
                    "raw_status": raw_status,
                    "status": status,
                    "event_state": event_state,
                    "alarm_level": alarm_level,
                    "event": display_result.get("event"),
                    "fall_score": round(float(display_result.get("fall_score") or 0.0), 4),
                    "raw_result": strip_heavy_fields(last_result) if args.save_frame_records else None,
                }
            )
            draw_result(frame, display_result)
            if args.save_review_frames and should_save_review_frame(display_result, frame_index):
                review_path = save_review_frame(frame, review_dir, frame_index, display_result)
                review_frames.append(
                    {
                        "frame": frame_index,
                        "time_s": round(frame_index / fps, 3),
                        "path": review_path,
                        "raw_status": raw_status,
                        "status": status,
                        "event_state": event_state,
                        "alarm_level": alarm_level,
                        "fall_score": round(float(display_result.get("fall_score") or 0.0), 4),
                    }
                )
            writer.write(frame)
            frame_index += 1
            bar.update(1)

    capture.release()
    writer.release()
    event_segments = summarize_timeline(frame_records, fps=fps)
    event_state_segments = summarize_field_timeline(frame_records, fps=fps, field="event_state")
    alarm_segments = summarize_field_timeline(frame_records, fps=fps, field="alarm_level")
    fall_segments = [item for item in event_segments if item["status"] == "fall"]
    suspected_segments = [item for item in event_segments if item["status"] == "suspected"]
    fallen_segments = [item for item in event_state_segments if item["event_state"] == "fallen"]
    falling_segments = [item for item in event_state_segments if item["event_state"] == "falling"]
    alert_segments = [item for item in alarm_segments if item["alarm_level"] in {"danger", "critical"}]
    summary = {
        "kind": "video",
        "source": str(source),
        "output": str(output),
        "frames": frame_index,
        "processed_frames": processed,
        "process_every": max(1, args.process_every),
        "fps": fps,
        "max_fall_score": round(max_score, 4),
        "status_counts": smoothed_status_counts,
        "raw_status_counts": raw_status_counts,
        "event_state_counts": event_state_counts,
        "alarm_counts": alarm_counts,
        "temporal_smoothing": {
            "enabled": smoother is not None,
            "event_window_frames": args.event_window_frames,
            "fall_confirm_frames": args.fall_confirm_frames,
            "fall_hold_frames": args.fall_hold_frames,
            "fall_score_threshold": args.fall_score_threshold,
            "suspected_score_threshold": args.suspected_score_threshold,
        },
        "event_segments": event_segments,
        "event_state_segments": event_state_segments,
        "alarm_segments": alarm_segments,
        "fall_segments": fall_segments,
        "falling_segments": falling_segments,
        "fallen_segments": fallen_segments,
        "alert_segments": alert_segments,
        "suspected_segments": suspected_segments,
        "fall_event_count": len(fall_segments),
        "fall_event_total_seconds": round(sum(float(item["duration_s"]) for item in fall_segments), 3),
        "alert_event_count": len(alert_segments),
        "alert_event_total_seconds": round(sum(float(item["duration_s"]) for item in alert_segments), 3),
        "suspected_event_total_seconds": round(sum(float(item["duration_s"]) for item in suspected_segments), 3),
        "review_frame_count": len(review_frames),
        "review_frames": review_frames[:200],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    if args.save_frame_records:
        summary["frame_records"] = frame_records
    return summary


def strip_heavy_fields(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in {"annotated_image_b64"}}


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output = (args.output or default_output_path(source)).expanduser().resolve()
    json_output = (args.json or output.with_suffix(output.suffix + ".json")).expanduser().resolve()

    print(f"[fall-demo] source: {source}")
    print(f"[fall-demo] output: {output}")
    service = FallFrameTestService(get_settings())
    warmup = service.warmup(imgsz=args.imgsz, posture_imgsz=args.posture_imgsz)
    print(f"[fall-demo] warmup: {json.dumps(warmup, ensure_ascii=False)}")
    if not warmup.get("ok"):
        return 2

    suffix = source.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        summary = run_image(service, source, output, args)
    elif suffix in VIDEO_SUFFIXES:
        summary = run_video(service, source, output, args)
    else:
        raise ValueError(f"Unsupported media suffix: {source.suffix}")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": service.status(),
        **summary,
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fall-demo] done: {output}")
    print(f"[fall-demo] summary: {json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
