from __future__ import annotations

import argparse
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


def fetch_status() -> dict[str, Any]:
    with urllib.request.urlopen("http://127.0.0.1:8000/status?camera_id=camera_01", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5.19E service-integrated human RTSP sampling.")
    parser.add_argument("--label", required=True, choices=["stand", "walk"])
    parser.add_argument("--duration-sec", type=int, default=180)
    parser.add_argument("--output-dir", default="logs/human_trial")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"phase5_19e_{args.label}_status.jsonl"
    summary_path = output_dir / f"phase5_19e_{args.label}_summary.json"

    rows: list[dict[str, Any]] = []
    started_at = time.time()
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for index in range(args.duration_sec):
            tick = time.time()
            try:
                status = fetch_status()
                pose = status.get("pose") or {}
                main = status.get("main_stream") or {}
                analysis = status.get("analysis_stream") or {}
                cameras = status.get("cameras") or [{}]
                camera = cameras[0] if cameras else {}
                row = {
                    "i": index,
                    "ts": time.time(),
                    "stream_state_main": main.get("stream_state"),
                    "stream_state_analysis": analysis.get("stream_state"),
                    "capture_fps_main": main.get("capture_fps"),
                    "capture_fps_analysis": analysis.get("capture_fps"),
                    "source_fps_main": camera.get("capture_process_source_fps"),
                    "frame_age_ms_main": main.get("frame_age_ms"),
                    "frame_age_ms_analysis": analysis.get("frame_age_ms"),
                    "detection_objects_count": pose.get("detection_objects_count"),
                    "tracking_objects_count": pose.get("tracking_objects_count"),
                    "target_objects_count": pose.get("target_objects_count"),
                    "pose_attempts": pose.get("pose_attempts"),
                    "pose_success": pose.get("pose_success"),
                    "pose_skip_reasons": pose.get("pose_skip_reasons"),
                    "pose_target_source": pose.get("pose_target_source"),
                    "capture_process_last_failure_reason": camera.get("capture_process_last_failure_reason"),
                    "capture_process_last_log": camera.get("capture_process_last_log"),
                }
            except Exception as exc:
                row = {"i": index, "ts": time.time(), "error": str(exc)}
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            time.sleep(max(0.0, 1.0 - (time.time() - tick)))

    summary = summarize(rows, time.time() - started_at)
    payload = {
        "label": args.label,
        "duration_sec": args.duration_sec,
        "jsonl_path": str(jsonl_path),
        "summary": summary,
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def summarize(rows: list[dict[str, Any]], duration_sec: float) -> dict[str, Any]:
    valid = [row for row in rows if "error" not in row]

    def ratio(predicate) -> float:
        if not valid:
            return 0.0
        return round(sum(1 for row in valid if predicate(row)) / len(valid), 4)

    def last_int(key: str) -> int:
        for row in reversed(valid):
            value = row.get(key)
            if isinstance(value, int):
                return value
        return 0

    pose_skip_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    for row in valid:
        for key, value in (row.get("pose_skip_reasons") or {}).items():
            pose_skip_counter[key] += int(value)
        source = row.get("pose_target_source")
        if source:
            source_counter[str(source)] += 1

    return {
        "duration_sec": round(duration_sec, 2),
        "valid_samples": len(valid),
        "stream_state_normal_ratio": ratio(
            lambda row: row.get("stream_state_main") == "connected" and row.get("stream_state_analysis") == "connected"
        ),
        "capture_fps_nonzero_ratio": ratio(
            lambda row: (row.get("capture_fps_main") or 0) > 0 and (row.get("capture_fps_analysis") or 0) > 0
        ),
        "detection_objects_nonzero_ratio": ratio(lambda row: (row.get("detection_objects_count") or 0) > 0),
        "tracking_objects_nonzero_ratio": ratio(lambda row: (row.get("tracking_objects_count") or 0) > 0),
        "target_objects_nonzero_ratio": ratio(lambda row: (row.get("target_objects_count") or 0) > 0),
        "pose_attempts_delta": max(0, last_int("pose_attempts") - (valid[0].get("pose_attempts") or 0 if valid else 0)),
        "pose_success_delta": max(0, last_int("pose_success") - (valid[0].get("pose_success") or 0 if valid else 0)),
        "pose_skip_reasons_merged": dict(pose_skip_counter),
        "pose_target_source_distribution": dict(source_counter),
    }


if __name__ == "__main__":
    raise SystemExit(main())
