from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

import cv2
import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CASES_PATH = ROOT / "tests" / "fixtures" / "replay_cases.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "logs" / "regression"
STATE_ORDER = {
    "normal": 0,
    "unstable": 1,
    "falling": 2,
    "fallen_candidate": 3,
    "fallen_confirmed": 4,
    "cooldown": 5,
}


@dataclass
class ReplayCase:
    case_id: str
    video_path: str
    label: str
    expected_max_state: str
    expected_confirmed: bool
    notes: str = ""


@dataclass
class ReplayResult:
    case_id: str
    label: str
    video_path: str
    confirmed: bool = False
    max_fall_state: str = "normal"
    max_fall_probability: float = 0.0
    first_confirmed_at_ms: float | None = None
    total_frames: int = 0
    processed_frames: int = 0
    avg_capture_fps: float = 0.0
    avg_detect_fps: float = 0.0
    avg_pose_fps: float = 0.0
    avg_latency_ms: float = 0.0
    worker_restart_count: int = 0
    watchdog_suppressed: bool = False
    passed: bool = False
    fail_reason: str | None = None
    states_seen: list[str] | None = None
    notes: str = ""


def configure_replay_environment() -> None:
    defaults = {
        "ENABLE_TRACKING": "true",
        "ENABLE_POSE": "true",
        "POSE_PROVIDER": "yolo",
        "ENABLE_BEHAVIOR": "true",
        "ENABLE_TEMPORAL": "true",
        "ENABLE_IDENTITY_BINDING": "false",
        "DETECTION_ENABLED": "true",
        "YOLO_CONFIDENCE": "0.35",
        "YOLO_IMGSZ": "640",
        "YOLO_POSE_CONFIDENCE": "0.25",
        "YOLO_POSE_IMGSZ": "320",
        "POSE_FPS": "1000",
        "POSE_SKIP_WHEN_INFERENCE_BUSY": "false",
        "WATCHDOG_ENABLED": "false",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


class ReplayRunner:
    def __init__(self, frame_stride: int, max_frames: int) -> None:
        configure_replay_environment()
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

    def run_case(self, case: ReplayCase) -> ReplayResult:
        video_path = (ROOT / case.video_path).resolve()
        result = ReplayResult(
            case_id=case.case_id,
            label=case.label,
            video_path=str(video_path),
            notes=case.notes,
        )
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            result.fail_reason = f"could not open video: {video_path}"
            return result

        camera_id = f"replay_{case.case_id}"
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        capture_intervals: list[float] = []
        detect_latencies: list[float] = []
        pose_latencies: list[float] = []
        total_latencies: list[float] = []
        states_seen: list[str] = []
        last_capture_tick: float | None = None
        first_confirmed_frame: int | None = None

        try:
            frame_index = 0
            while frame_index < self.max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                result.total_frames += 1
                now = time.perf_counter()
                if last_capture_tick is not None:
                    capture_intervals.append(now - last_capture_tick)
                last_capture_tick = now

                if frame_index % self.frame_stride != 0:
                    frame_index += 1
                    continue

                loop_started = time.perf_counter()
                detect_started = time.perf_counter()
                objects = self.detector.detect(frame)
                detect_latencies.append((time.perf_counter() - detect_started) * 1000)

                objects = self.tracking.enrich(camera_id, objects, frame=frame)

                pose_started = time.perf_counter()
                objects = self.pose.enrich(camera_id, frame, objects)
                pose_latencies.append((time.perf_counter() - pose_started) * 1000)

                objects = self.behavior.enrich(camera_id, objects)
                objects = self.temporal.enrich(camera_id, objects)
                total_latencies.append((time.perf_counter() - loop_started) * 1000)
                result.processed_frames += 1

                for item in objects:
                    temporal = item.temporal or {}
                    decision = item.fall_decision or {}
                    probability = float(temporal.get("fall_probability") or 0.0)
                    state = str(decision.get("fall_state") or "normal")
                    result.max_fall_probability = max(result.max_fall_probability, probability)
                    if state not in states_seen:
                        states_seen.append(state)
                    if STATE_ORDER.get(state, 0) > STATE_ORDER.get(result.max_fall_state, 0):
                        result.max_fall_state = state
                    if state == "fallen_confirmed":
                        result.confirmed = True
                        if first_confirmed_frame is None:
                            first_confirmed_frame = frame_index

                frame_index += 1
        except Exception as exc:
            result.fail_reason = str(exc)
        finally:
            cap.release()

        result.states_seen = states_seen
        if first_confirmed_frame is not None:
            fps = source_fps if source_fps > 0 else 30.0
            result.first_confirmed_at_ms = round(first_confirmed_frame / fps * 1000, 2)
        result.avg_capture_fps = estimate_capture_fps(capture_intervals, source_fps)
        result.avg_detect_fps = estimate_stage_fps(detect_latencies)
        result.avg_pose_fps = estimate_stage_fps(pose_latencies)
        result.avg_latency_ms = round(mean(total_latencies), 2) if total_latencies else 0.0
        result.worker_restart_count = 0
        result.watchdog_suppressed = False
        apply_expectations(case, result)
        return result


def estimate_capture_fps(intervals: list[float], fallback_fps: float) -> float:
    if intervals:
        avg = mean(intervals)
        if avg > 0:
            return round(1.0 / avg, 2)
    return round(fallback_fps or 0.0, 2)


def estimate_stage_fps(latencies_ms: list[float]) -> float:
    if not latencies_ms:
        return 0.0
    avg_ms = mean(latencies_ms)
    if avg_ms <= 0:
        return 0.0
    return round(1000.0 / avg_ms, 2)


def apply_expectations(case: ReplayCase, result: ReplayResult) -> None:
    reasons: list[str] = []
    expected_rank = STATE_ORDER.get(case.expected_max_state, 0)
    actual_rank = STATE_ORDER.get(result.max_fall_state, 0)
    if case.expected_confirmed != result.confirmed:
        reasons.append(f"expected_confirmed={case.expected_confirmed} actual={result.confirmed}")
    if case.label in {"normal", "hard_negative"} and actual_rank > expected_rank:
        reasons.append(f"max_state {result.max_fall_state} exceeded expected {case.expected_max_state}")
    if case.label == "fall" and actual_rank < expected_rank:
        reasons.append(f"max_state {result.max_fall_state} below expected {case.expected_max_state}")
    if result.worker_restart_count > 0:
        reasons.append(f"worker_restart_count={result.worker_restart_count}")
    if result.watchdog_suppressed:
        reasons.append("watchdog_suppressed=true")
    if result.fail_reason:
        reasons.append(result.fail_reason)
    result.passed = not reasons
    result.fail_reason = "; ".join(reasons) if reasons else None


def load_cases(path: Path) -> list[ReplayCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases = raw.get("cases") or []
    return [ReplayCase(**item) for item in cases]


def render_markdown(results: list[ReplayResult], summary: dict[str, Any]) -> str:
    lines = [
        "# Replay Regression Report",
        "",
        "This replay run uses fixed videos and the current Phase 5 rule-based pipeline.",
        "It does not train models, does not use GRU/LSTM, and does not call alert POST/snapshot paths.",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Generated at: {summary['generated_at']}",
        "",
        "## Cases",
        "",
        "| Case | Label | Pass | Max State | Max Prob | Confirmed | Frames | Processed | Detect FPS | Pose FPS | Avg Latency | Fail Reason |",
        "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in results:
        lines.append(
            "| {case} | {label} | {passed} | {state} | {prob:.2f} | {confirmed} | {frames} | {processed} | {detect:.2f} | {pose:.2f} | {latency:.2f} | {reason} |".format(
                case=item.case_id,
                label=item.label,
                passed="PASS" if item.passed else "FAIL",
                state=item.max_fall_state,
                prob=item.max_fall_probability,
                confirmed=item.confirmed,
                frames=item.total_frames,
                processed=item.processed_frames,
                detect=item.avg_detect_fps,
                pose=item.avg_pose_fps,
                latency=item.avg_latency_ms,
                reason=item.fail_reason or "",
            )
        )
    lines.extend(["", "## Notes", ""])
    for item in results:
        if item.notes:
            lines.append(f"- `{item.case_id}`: {item.notes}")
    return "\n".join(lines) + "\n"


def write_report(results: list[ReplayResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "passed": sum(1 for item in results if item.passed),
        "failed": sum(1 for item in results if not item.passed),
    }
    payload = {
        "summary": summary,
        "results": [asdict(item) for item in results],
    }
    (output_dir / "regression_report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "regression_report.md").write_text(render_markdown(results, summary), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixed-video replay regression for Phase 5.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--frame-stride", type=int, default=5)
    parser.add_argument("--max-frames", type=int, default=300)
    parser.add_argument("--case-id", action="append", default=None)
    args = parser.parse_args()

    cases = load_cases(Path(args.cases))
    if args.case_id:
        selected = set(args.case_id)
        cases = [item for item in cases if item.case_id in selected]
    if not cases:
        raise SystemExit("No replay cases selected.")

    runner = ReplayRunner(frame_stride=args.frame_stride, max_frames=args.max_frames)
    results = [runner.run_case(case) for case in cases]
    write_report(results, Path(args.output_dir))
    failed = [item for item in results if not item.passed]
    print(json.dumps({"case_count": len(results), "failed": [item.case_id for item in failed]}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
