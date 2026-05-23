from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cv2


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATASETS_DIR = ROOT / "datasets"
MANIFEST_PATH = DATASETS_DIR / "dataset_manifest.json"
LOG_DIR = ROOT / "logs" / "phase5_dataset_eval"
DOC_REPORT_PATH = ROOT / "docs" / "phase5_dataset_report.md"


@dataclass
class VideoEvalResult:
    video: str
    dataset: str
    label: str
    frames: int = 0
    sampled_frames: int = 0
    max_probability: float = 0.0
    states_seen: list[str] = field(default_factory=list)
    confirmed: bool = False
    risk_peak: str = "low"
    first_candidate_frame: int | None = None
    first_confirmed_frame: int | None = None
    max_velocity_y: float = 0.0
    max_delta_y: float = 0.0
    max_total_descent_hint: float = 0.0
    max_aspect_ratio: float = 0.0
    pose_available_frames: int = 0
    temporal_frames: int = 0
    last_error: str | None = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Phase 5 temporal rules on public fall datasets.")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH))
    parser.add_argument("--dataset", default="ur_fall")
    parser.add_argument("--limit-normal", type=int, default=5)
    parser.add_argument("--limit-fall", type=int, default=5)
    parser.add_argument("--frame-stride", type=int, default=5)
    parser.add_argument("--max-frames", type=int, default=500)
    parser.add_argument("--download", action="store_true", help="Run dataset downloader before evaluation.")
    args = parser.parse_args()

    configure_eval_environment()
    if args.download or not Path(args.manifest).exists():
        from scripts.download_fall_datasets import main as download_main

        download_main()

    manifest = load_manifest(Path(args.manifest))
    selected = select_videos(manifest, args.dataset, args.limit_normal, args.limit_fall)
    if not selected:
        raise SystemExit("No videos selected. Run scripts/download_fall_datasets.py first.")

    evaluator = Phase5OfflineEvaluator(frame_stride=args.frame_stride, max_frames=args.max_frames)
    results = [evaluator.evaluate(dataset, video, label) for dataset, video, label in selected]
    summary = summarize(results, manifest)
    write_outputs(results, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def configure_eval_environment() -> None:
    defaults = {
        "ENABLE_TRACKING": "true",
        "ENABLE_POSE": "true",
        "POSE_PROVIDER": "yolo",
        "ENABLE_BEHAVIOR": "true",
        "ENABLE_TEMPORAL": "true",
        "ENABLE_IDENTITY_BINDING": "false",
        "YOLO_CONFIDENCE": "0.35",
        "YOLO_IMGSZ": "640",
        "YOLO_POSE_CONFIDENCE": "0.25",
        "YOLO_POSE_IMGSZ": "640",
        "POSE_FPS": "1000",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def select_videos(manifest: dict, dataset: str, limit_normal: int, limit_fall: int) -> list[tuple[str, str, str]]:
    entry = manifest.get(dataset, {})
    if not entry.get("available"):
        return []
    labels = entry.get("labels", {})
    fall = [(dataset, video, label) for video, label in labels.items() if label == "fall"]
    normal = [(dataset, video, label) for video, label in labels.items() if label != "fall"]
    return normal[:limit_normal] + fall[:limit_fall]


class Phase5OfflineEvaluator:
    def __init__(self, frame_stride: int, max_frames: int) -> None:
        from app.core.config import get_settings
        from app.detection.object_detector import YoloPersonDetector
        from app.services.behavior_service import BehaviorService
        from app.services.pose_service import PoseService
        from app.services.temporal_service import TemporalService
        from app.services.tracking_service import TrackingService

        self.settings = get_settings()
        self.detector = YoloPersonDetector(self.settings)
        self.tracking = TrackingService(self.settings)
        self.pose = PoseService(self.settings)
        self.behavior = BehaviorService(self.settings)
        self.temporal = TemporalService(self.settings)
        self.frame_stride = max(1, frame_stride)
        self.max_frames = max_frames

    def evaluate(self, dataset: str, video: str, label: str) -> VideoEvalResult:
        camera_id = f"eval_{dataset}_{Path(video).stem}"
        video_path = DATASETS_DIR / dataset / "videos" / video
        result = VideoEvalResult(video=video, dataset=dataset, label=label)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            result.last_error = f"could not open video: {video_path}"
            return result

        states = []
        risks = []
        try:
            frame_index = 0
            while frame_index < self.max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                result.frames += 1
                if frame_index % self.frame_stride != 0:
                    frame_index += 1
                    continue

                result.sampled_frames += 1
                objects = self.detector.detect(frame)
                objects = self.tracking.enrich(camera_id, objects, frame=frame)
                objects = self.pose.enrich(camera_id, frame, objects)
                objects = self.behavior.enrich(camera_id, objects)
                objects = self.temporal.enrich(camera_id, objects)

                for obj in objects:
                    temporal = obj.temporal or {}
                    features = temporal.get("features") or {}
                    decision = obj.fall_decision or {}
                    alarm = obj.alarm_preview or {}
                    probability = float(temporal.get("fall_probability") or 0.0)
                    result.max_probability = max(result.max_probability, probability)
                    if temporal:
                        result.temporal_frames += 1
                    result.max_velocity_y = max(result.max_velocity_y, float(features.get("velocity_y") or 0.0))
                    result.max_delta_y = max(result.max_delta_y, float(features.get("delta_y") or 0.0))
                    result.max_aspect_ratio = max(result.max_aspect_ratio, float(features.get("aspect_ratio") or 0.0))
                    if features.get("pose_available"):
                        result.pose_available_frames += 1
                    state = decision.get("fall_state")
                    risk = alarm.get("risk_level") or decision.get("risk_level")
                    if state:
                        states.append(state)
                    if risk:
                        risks.append(risk)
                    if state == "fallen_candidate" and result.first_candidate_frame is None:
                        result.first_candidate_frame = frame_index
                    if state == "fallen_confirmed":
                        result.confirmed = True
                        if result.first_confirmed_frame is None:
                            result.first_confirmed_frame = frame_index

                frame_index += 1
        except Exception as exc:
            result.last_error = str(exc)
        finally:
            cap.release()

        result.states_seen = list(dict.fromkeys(states))
        result.risk_peak = peak_risk(risks)
        return result


def peak_risk(risks: Iterable[str]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3, "cooldown": 1}
    peak = "low"
    for risk in risks:
        if order.get(risk, 0) > order.get(peak, 0):
            peak = risk
    return peak


def summarize(results: list[VideoEvalResult], manifest: dict) -> dict:
    normal = [item for item in results if item.label != "fall"]
    fall = [item for item in results if item.label == "fall"]

    normal_stats = state_counts(normal)
    fall_stats = state_counts(fall)
    detected_falls = sum(1 for item in fall if "falling" in item.states_seen or item.confirmed or "fallen_candidate" in item.states_seen)
    missed_falls = len(fall) - detected_falls
    normal_unstable = sum(1 for item in normal if "unstable" in item.states_seen)
    normal_falling = sum(1 for item in normal if "falling" in item.states_seen)
    normal_candidate = sum(1 for item in normal if "fallen_candidate" in item.states_seen)
    normal_confirmed = sum(1 for item in normal if item.confirmed)
    fall_falling = sum(1 for item in fall if "falling" in item.states_seen)
    fall_candidate = sum(1 for item in fall if "fallen_candidate" in item.states_seen)
    fall_confirmed = sum(1 for item in fall if item.confirmed)

    suggestions = make_suggestions(normal, fall)
    return {
        "datasets": {
            name: {
                "available": entry.get("available", False),
                "video_count": len(entry.get("videos", [])),
                "failed_reason": entry.get("failed_reason"),
            }
            for name, entry in manifest.items()
        },
        "tested_videos": len(results),
        "normal_videos": len(normal),
        "fall_videos": len(fall),
        "normal_state_counts": normal_stats,
        "fall_state_counts": fall_stats,
        "adl_unstable_count": normal_unstable,
        "adl_unstable_rate": round(normal_unstable / len(normal), 4) if normal else 0.0,
        "adl_falling_fp": normal_falling,
        "false_positive_confirmed": normal_confirmed,
        "false_positive_candidate": normal_candidate,
        "adl_confirmed_fp": normal_confirmed,
        "adl_candidate_fp": normal_candidate,
        "fall_falling_count": fall_falling,
        "fall_falling_recall": round(fall_falling / len(fall), 4) if fall else 0.0,
        "fall_candidate_count": fall_candidate,
        "fall_candidate_recall": round(fall_candidate / len(fall), 4) if fall else 0.0,
        "fall_confirmed_count": fall_confirmed,
        "fall_confirmed_recall": round(fall_confirmed / len(fall), 4) if fall else 0.0,
        "fall_detected": detected_falls,
        "fall_missed": missed_falls,
        "suggestions": suggestions,
    }


def state_counts(results: list[VideoEvalResult]) -> dict:
    counts = Counter()
    for item in results:
        for state in item.states_seen:
            counts[state] += 1
    return dict(counts)


def make_suggestions(normal: list[VideoEvalResult], fall: list[VideoEvalResult]) -> list[str]:
    suggestions: list[str] = []
    if any(item.confirmed for item in normal):
        suggestions.append("Normal videos reached fallen_confirmed: increase FALL_CONFIRM_FRAMES or FALL_STILL_MS.")
    if any("fallen_candidate" in item.states_seen for item in normal):
        suggestions.append("Normal videos reached fallen_candidate: require stronger rapid descent evidence in fall_state_machine.py.")
    if any("falling" in item.states_seen for item in normal):
        suggestions.append("Normal videos reached falling: consider raising FALLING_PROB_THRESHOLD or reducing low-posture weights.")
    missed = [item for item in fall if not item.confirmed and "fallen_candidate" not in item.states_seen and "falling" not in item.states_seen]
    if missed:
        suggestions.append("Some fall videos were missed: lower rapid descent thresholds or add bbox center-y trend features.")
    if not suggestions:
        suggestions.append("No obvious rule issue from this sample; run more videos and inspect edge cases.")
    suggestions.append("Editable files for next tuning: app/temporal/mock_sequence_model.py and app/temporal/fall_state_machine.py.")
    return suggestions


def write_outputs(results: list[VideoEvalResult], summary: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs").mkdir(parents=True, exist_ok=True)

    (LOG_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with (LOG_DIR / "per_video.jsonl").open("w", encoding="utf-8") as output:
        for item in results:
            output.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")
    DOC_REPORT_PATH.write_text(render_report(results, summary), encoding="utf-8")


def render_report(results: list[VideoEvalResult], summary: dict) -> str:
    lines = [
        "# Phase 5 Dataset Evaluation Report",
        "",
        "This report evaluates the current rule-based Temporal Decision Layer.",
        "It does not train models, does not use GRU/LSTM, and does not modify runtime rules.",
        "",
        "## Summary",
        "",
        f"- Tested videos: {summary['tested_videos']}",
        f"- Normal videos: {summary['normal_videos']}",
        f"- Fall videos: {summary['fall_videos']}",
        f"- False positive confirmed: {summary['false_positive_confirmed']}",
        f"- False positive candidate: {summary['false_positive_candidate']}",
        f"- Fall detected: {summary['fall_detected']}",
        f"- Fall missed: {summary['fall_missed']}",
        f"- ADL unstable rate: {summary['adl_unstable_count']}/{summary['normal_videos']} ({summary['adl_unstable_rate']:.2%})",
        f"- ADL candidate FP: {summary['adl_candidate_fp']}",
        f"- ADL confirmed FP: {summary['adl_confirmed_fp']}",
        f"- Fall falling recall: {summary['fall_falling_count']}/{summary['fall_videos']} ({summary['fall_falling_recall']:.2%})",
        f"- Fall candidate recall: {summary['fall_candidate_count']}/{summary['fall_videos']} ({summary['fall_candidate_recall']:.2%})",
        f"- Fall confirmed recall: {summary['fall_confirmed_count']}/{summary['fall_videos']} ({summary['fall_confirmed_recall']:.2%})",
        "",
        "## Per Video",
        "",
    ]
    for item in results:
        lines.append(
            f"- `{item.dataset}/{item.video}` label={item.label} frames={item.frames} "
            f"sampled={item.sampled_frames} max_prob={item.max_probability:.2f} "
            f"states={item.states_seen} confirmed={item.confirmed} risk_peak={item.risk_peak} "
            f"max_vy={item.max_velocity_y:.1f} max_dy={item.max_delta_y:.1f} "
            f"max_ratio={item.max_aspect_ratio:.2f} pose_frames={item.pose_available_frames}"
        )
    lines.extend(["", "## Suggestions", ""])
    lines.extend(f"- {item}" for item in summary["suggestions"])
    lines.extend(["", "## Artifacts", "", f"- `{LOG_DIR / 'summary.json'}`", f"- `{LOG_DIR / 'per_video.jsonl'}`"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
