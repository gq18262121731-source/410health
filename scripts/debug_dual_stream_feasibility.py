from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.camera.frame_buffer import FrameBuffer
from app.camera.source_models import CameraSourceConfig
from app.camera.subprocess_capture_worker import SubprocessCaptureWorker
from app.core.config import Settings


DEFAULT_MAIN_URL = "rtsp://admin:410410410@192.168.8.254:10554/tcp/av0_0"
DEFAULT_ANALYSIS_URL = "rtsp://admin:410410410@192.168.8.254:10554/tcp/av0_1"
OUTPUT_PATH = ROOT / "logs" / "runtime_debug" / "dual_stream_feasibility.json"


def _gpu_sample() -> dict:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
        util, memory = [int(part.strip()) for part in output.strip().split(",", 1)]
        return {"gpu_util": util, "gpu_memory_mb": memory}
    except Exception:
        return {"gpu_util": None, "gpu_memory_mb": None}


def _process_sample() -> dict:
    try:
        import psutil

        process = psutil.Process()
        return {
            "process_memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "process_cpu_percent": process.cpu_percent(interval=None),
        }
    except Exception:
        return {"process_memory_mb": None, "process_cpu_percent": None}


def _status_payload(worker: SubprocessCaptureWorker) -> dict:
    status = worker.status()
    return {
        "connected": status.connected,
        "stream_state": status.stream_state,
        "frame_age_ms": status.frame_age_ms,
        "capture_fps": status.capture_fps,
        "process_alive": status.capture_process_alive,
        "process_pid": status.capture_process_pid,
        "restart_count": status.capture_process_restart_count,
        "last_error": status.last_error,
        "process_last_error": status.capture_process_last_error,
        "process_last_exit_code": status.capture_process_last_exit_code,
        "output_width": status.capture_output_width or status.frame_width,
        "output_height": status.capture_output_height or status.frame_height,
        "ipc_decode_errors": status.capture_ipc_decode_errors,
        "ipc_dropped_frames": status.capture_ipc_dropped_frames,
    }


def _avg(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 2) if values else None


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def _summarize_stream(rows: list[dict], name: str) -> dict:
    states = [row[name] for row in rows]
    connected = [state for state in states if state["connected"]]
    frame_ages = [
        float(state["frame_age_ms"])
        for state in states
        if state.get("frame_age_ms") is not None
    ]
    fps_values = [
        float(state["capture_fps"])
        for state in states
        if state.get("capture_fps") is not None
    ]
    restart_start = states[0].get("restart_count") or 0
    restart_end = states[-1].get("restart_count") or 0
    return {
        "connected_ratio": round(len(connected) / len(states), 4) if states else 0.0,
        "frame_age_over_3000_count": len([age for age in frame_ages if age > 3000]),
        "max_frame_age_ms": _max(frame_ages),
        "avg_capture_fps": _avg(fps_values),
        "restart_delta": restart_end - restart_start,
        "final_stream_state": states[-1].get("stream_state") if states else None,
        "final_last_error": states[-1].get("last_error") if states else None,
        "final_process_last_error": states[-1].get("process_last_error") if states else None,
        "final_output_width": states[-1].get("output_width") if states else None,
        "final_output_height": states[-1].get("output_height") if states else None,
        "ipc_decode_error_delta": (states[-1].get("ipc_decode_errors") or 0)
        - (states[0].get("ipc_decode_errors") or 0)
        if states
        else 0,
    }


def run(args: argparse.Namespace) -> dict:
    settings = Settings()
    main_buffer = FrameBuffer("dual_main")
    analysis_buffer = FrameBuffer("dual_analysis")
    main_worker = SubprocessCaptureWorker(
        config=CameraSourceConfig(camera_id="dual_main", source_url=args.main_url),
        frame_buffer=main_buffer,
        settings=settings,
    )
    analysis_worker = SubprocessCaptureWorker(
        config=CameraSourceConfig(camera_id="dual_analysis", source_url=args.analysis_url),
        frame_buffer=analysis_buffer,
        settings=settings,
    )

    rows: list[dict] = []
    main_worker.start()
    analysis_worker.start()
    started_at = time.time()
    try:
        for index in range(1, args.duration_sec + 1):
            gpu = _gpu_sample() if index == 1 or index % args.resource_interval_sec == 0 else {}
            proc = _process_sample() if index == 1 or index % args.resource_interval_sec == 0 else {}
            rows.append(
                {
                    "i": index,
                    "elapsed_sec": round(time.time() - started_at, 2),
                    "main": _status_payload(main_worker),
                    "analysis": _status_payload(analysis_worker),
                    **gpu,
                    **proc,
                }
            )
            time.sleep(1)
    finally:
        main_worker.stop()
        analysis_worker.stop()

    gpu_values = [row["gpu_util"] for row in rows if row.get("gpu_util") is not None]
    gpu_memory_values = [
        row["gpu_memory_mb"] for row in rows if row.get("gpu_memory_mb") is not None
    ]
    memory_values = [
        row["process_memory_mb"]
        for row in rows
        if row.get("process_memory_mb") is not None
    ]
    summary = {
        "duration_sec": args.duration_sec,
        "sample_count": len(rows),
        "main_url_masked": _mask(args.main_url),
        "analysis_url_masked": _mask(args.analysis_url),
        "main": _summarize_stream(rows, "main"),
        "analysis": _summarize_stream(rows, "analysis"),
        "gpu_util_avg": _avg([float(value) for value in gpu_values]),
        "gpu_memory_max_mb": _max([float(value) for value in gpu_memory_values]),
        "process_memory_start_mb": memory_values[0] if memory_values else None,
        "process_memory_end_mb": memory_values[-1] if memory_values else None,
        "process_memory_delta_mb": round(memory_values[-1] - memory_values[0], 2)
        if len(memory_values) >= 2
        else None,
    }
    return {"summary": summary, "rows": rows}


def _mask(url: str) -> str:
    import re

    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 5.15A dual RTSP feasibility test")
    parser.add_argument("--main-url", default=DEFAULT_MAIN_URL)
    parser.add_argument("--analysis-url", default=DEFAULT_ANALYSIS_URL)
    parser.add_argument("--duration-sec", type=int, default=600)
    parser.add_argument("--resource-interval-sec", type=int, default=5)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
