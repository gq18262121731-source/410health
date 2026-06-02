from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path


OUTPUT = Path("logs/runtime_debug/phase5_19d_rtsp_pose_status.json")


def fetch_status() -> dict:
    with urllib.request.urlopen("http://127.0.0.1:8000/status?camera_id=camera_01", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    rows = []
    for index in range(30):
        started = time.time()
        try:
            status = fetch_status()
            pose = status.get("pose") or {}
            pipeline = status.get("pipeline") or {}
            rows.append(
                {
                    "i": index,
                    "main_state": (status.get("main_stream") or {}).get("stream_state"),
                    "analysis_state": (status.get("analysis_stream") or {}).get("stream_state"),
                    "main_age": (status.get("main_stream") or {}).get("frame_age_ms"),
                    "analysis_age": (status.get("analysis_stream") or {}).get("frame_age_ms"),
                    "detection_fps": pipeline.get("detection_worker_fps"),
                    "tracking_fps": pipeline.get("tracking_worker_fps"),
                    "publish_fps": pipeline.get("result_publish_fps"),
                    "detection_objects": pose.get("detection_objects_count"),
                    "tracking_objects": pose.get("tracking_objects_count"),
                    "target_objects": pose.get("target_objects_count"),
                    "pose_attempts": pose.get("pose_attempts"),
                    "pose_success": pose.get("pose_success"),
                    "pose_fps": pose.get("pose_fps"),
                    "pose_target_source": pose.get("pose_target_source"),
                    "fallback_used_count": pose.get("fallback_used_count"),
                    "last_fallback_reason": pose.get("last_fallback_reason"),
                    "pose_objects_count": pose.get("pose_objects_count"),
                    "pose_result_writeback_ok": pose.get("pose_result_writeback_ok"),
                    "pose_skip_reasons": pose.get("pose_skip_reasons"),
                }
            )
        except Exception as exc:
            rows.append({"i": index, "error": str(exc)})
        elapsed = time.time() - started
        time.sleep(max(0.0, 2.0 - elapsed))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rows[-1] if rows else {}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
