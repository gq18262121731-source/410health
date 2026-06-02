from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_status() -> dict[str, Any]:
    with urllib.request.urlopen(
        "http://127.0.0.1:8000/status?camera_id=camera_01",
        timeout=3,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def ps_text(command: str) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def get_listener_pid(port: int) -> int | None:
    output = ps_text(
        f"(Get-NetTCPConnection -LocalPort {port} -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -First 1 "
        "-ExpandProperty OwningProcess)"
    )
    try:
        return int(output.splitlines()[-1].strip()) if output else None
    except Exception:
        return None


def get_memory_mb(pid: int | None) -> float | None:
    if not pid:
        return None
    output = ps_text(
        f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
        "if ($p) { [math]::Round($p.WorkingSet64/1MB,2) }"
    )
    try:
        return float(output.splitlines()[-1].strip()) if output else None
    except Exception:
        return None


def get_process_cpu_percent(pid: int | None) -> float | None:
    if not pid:
        return None
    try:
        output = ps_text(
            (
                f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue;"
                "if ($p) { [math]::Round($p.CPU, 2) }"
            )
        )
        if not output:
            return None
        return float(output.splitlines()[-1].strip())
    except Exception:
        return None


def get_total_cpu_percent() -> float | None:
    output = ps_text("(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples[0].CookedValue")
    try:
        return round(float(output.splitlines()[-1].strip()), 2) if output else None
    except Exception:
        return None


def get_gpu() -> dict[str, float | None]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {"gpu_util": None, "gpu_memory_mb": None}
        first = result.stdout.strip().splitlines()[0]
        util, memory = [part.strip() for part in first.split(",")[:2]]
        return {"gpu_util": float(util), "gpu_memory_mb": float(memory)}
    except Exception:
        return {"gpu_util": None, "gpu_memory_mb": None}


def finite_values(values: list[Any]) -> list[float]:
    return [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(float(value))
    ]


def average(values: list[Any]) -> float | None:
    numeric = finite_values(values)
    return round(sum(numeric) / len(numeric), 3) if numeric else None


def minimum(values: list[Any]) -> float | None:
    numeric = finite_values(values)
    return round(min(numeric), 3) if numeric else None


def maximum(values: list[Any]) -> float | None:
    numeric = finite_values(values)
    return round(max(numeric), 3) if numeric else None


def count_truthy(values: list[Any]) -> int:
    return sum(1 for value in values if value)


def restart_delta(valid: list[dict[str, Any]], key: str) -> int | None:
    if not valid:
        return None
    return int(valid[-1].get(key) or 0) - int(valid[0].get(key) or 0)


def summarize(samples: list[dict[str, Any]], failures: list[dict[str, Any]], started_at: float) -> dict[str, Any]:
    valid = [sample for sample in samples if "status_error" not in sample]
    vision_cpu_seconds = finite_values([sample.get("vision_cpu_seconds") for sample in samples])
    duration = time.monotonic() - started_at
    approx_cpu_percent = None
    if len(vision_cpu_seconds) >= 2 and duration > 0:
        logical = os_cpu_count()
        if logical > 0:
            approx_cpu_percent = round(((vision_cpu_seconds[-1] - vision_cpu_seconds[0]) / (duration * logical)) * 100, 3)
    summary: dict[str, Any] = {
        "duration_sec": round(time.monotonic() - started_at, 2),
        "sample_count": len(valid),
        "status_failures": len(failures),
        "main_max_frame_age_ms": maximum([sample.get("main_frame_age_ms") for sample in valid]),
        "main_frame_age_over_3000_count": count_truthy(
            [(sample.get("main_frame_age_ms") or 0) > 3000 for sample in valid]
        ),
        "analysis_max_frame_age_ms": maximum([sample.get("analysis_frame_age_ms") for sample in valid]),
        "analysis_frame_age_over_3000_count": count_truthy(
            [(sample.get("analysis_frame_age_ms") or 0) > 3000 for sample in valid]
        ),
        "tracking_worker_fps_avg": average([sample.get("tracking_worker_fps") for sample in valid]),
        "tracking_worker_fps_min": minimum([sample.get("tracking_worker_fps") for sample in valid]),
        "result_publish_fps_avg": average([sample.get("result_publish_fps") for sample in valid]),
        "result_publish_fps_min": minimum([sample.get("result_publish_fps") for sample in valid]),
        "detection_worker_fps_avg": average([sample.get("detection_worker_fps") for sample in valid]),
        "detection_worker_fps_min": minimum([sample.get("detection_worker_fps") for sample in valid]),
        "detection_latency_avg_ms": average([sample.get("detection_latency_ms") for sample in valid]),
        "detection_latency_p95_ms": percentile([sample.get("detection_latency_ms") for sample in valid], 95),
        "detection_lock_wait_avg_ms": average([sample.get("detection_lock_wait_avg_ms") for sample in valid]),
        "detection_lock_wait_p95_ms": maximum([sample.get("detection_lock_wait_p95_ms") for sample in valid]),
        "pose_fps_avg": average([sample.get("pose_fps") for sample in valid]),
        "pose_latency_avg_ms": average([sample.get("pose_latency_ms") for sample in valid]),
        "pose_latency_p95_ms": percentile([sample.get("pose_latency_ms") for sample in valid], 95),
        "pose_lock_wait_avg_ms": average([sample.get("pose_lock_wait_avg_ms") for sample in valid]),
        "pose_lock_wait_p95_ms": maximum([sample.get("pose_lock_wait_p95_ms") for sample in valid]),
        "pose_skipped_due_to_busy_delta": restart_delta(valid, "pose_skipped_due_to_busy"),
        "pipeline_errors": count_truthy([sample.get("pipeline_last_error") for sample in valid]),
        "gpu_util_avg": average([sample.get("gpu_util") for sample in samples]),
        "gpu_util_max": maximum([sample.get("gpu_util") for sample in samples]),
        "cpu_util_avg": average([sample.get("vision_cpu_percent") for sample in samples]),
        "cpu_util_max": maximum([sample.get("vision_cpu_percent") for sample in samples]),
        "cpu_util_approx_process_percent": approx_cpu_percent,
        "system_cpu_avg": average([sample.get("system_cpu_percent") for sample in samples]),
    }
    return summary


def percentile(values: list[Any], q: float) -> float | None:
    numeric = finite_values(values)
    if not numeric:
        return None
    ordered = sorted(numeric)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * (q / 100.0)
    low = int(math.floor(pos))
    high = int(math.ceil(pos))
    if low == high:
        return round(ordered[low], 3)
    weight = pos - low
    return round(ordered[low] + (ordered[high] - ordered[low]) * weight, 3)


def run(duration_sec: int, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vision_pid = get_listener_pid(8000)
    identity_pid = get_listener_pid(8100)
    started = time.monotonic()
    samples: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for index in range(duration_sec):
        tick = time.monotonic()
        sample: dict[str, Any] = {"i": index + 1, "at": now_iso()}
        try:
            status = get_status()
            main = status.get("main_stream") or {}
            analysis = status.get("analysis_stream") or {}
            pipeline = status.get("pipeline") or {}
            pose = status.get("pose") or {}
            detection = (status.get("detection") or [{}])[0]

            sample.update(
                {
                    "main_frame_age_ms": main.get("frame_age_ms"),
                    "analysis_frame_age_ms": analysis.get("frame_age_ms"),
                    "main_restart_count": main.get("restart_count"),
                    "analysis_restart_count": analysis.get("restart_count"),
                    "detection_worker_fps": pipeline.get("detection_worker_fps"),
                    "tracking_worker_fps": pipeline.get("tracking_worker_fps"),
                    "result_publish_fps": pipeline.get("result_publish_fps"),
                    "pipeline_last_error": pipeline.get("last_error"),
                    "detection_latency_ms": detection.get("inference_latency_ms"),
                    "detection_lock_wait_avg_ms": detection.get("lock_wait_avg_ms"),
                    "detection_lock_wait_p95_ms": detection.get("lock_wait_p95_ms"),
                    "pose_fps": pose.get("pose_fps"),
                    "pose_latency_ms": pose.get("last_inference_latency_ms"),
                    "pose_lock_wait_avg_ms": pose.get("lock_wait_avg_ms"),
                    "pose_lock_wait_p95_ms": pose.get("lock_wait_p95_ms"),
                    "pose_skipped_due_to_busy": pose.get("skipped_due_to_busy"),
                }
            )
        except Exception as exc:
            sample["status_error"] = repr(exc)
            failures.append({"i": index + 1, "at": sample["at"], "error": repr(exc)})

        if index % 5 == 0:
            sample.update(get_gpu())
            sample["vision_memory_mb"] = get_memory_mb(vision_pid)
            sample["identity_memory_mb"] = get_memory_mb(identity_pid)
            sample["vision_cpu_seconds"] = get_process_cpu_percent(vision_pid)
            sample["vision_cpu_percent"] = None
            sample["system_cpu_percent"] = get_total_cpu_percent()

        samples.append(sample)
        elapsed = time.monotonic() - tick
        time.sleep(max(0, 1.0 - elapsed))

    summary = summarize(samples, failures, started)
    payload = {
        "started_at": samples[0]["at"] if samples else None,
        "ended_at": now_iso(),
        "vision_pid": vision_pid,
        "identity_pid": identity_pid,
        "summary": summary,
        "failures": failures,
        "samples": samples,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-sec", type=int, default=300)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.duration_sec, Path(args.output))


def os_cpu_count() -> int:
    import os

    return os.cpu_count() or 1


if __name__ == "__main__":
    main()
