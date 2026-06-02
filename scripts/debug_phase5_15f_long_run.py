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
    vision_memory = finite_values([sample.get("vision_memory_mb") for sample in samples])
    identity_memory = finite_values([sample.get("identity_memory_mb") for sample in samples])

    summary: dict[str, Any] = {
        "duration_sec": round(time.monotonic() - started_at, 2),
        "sample_count": len(valid),
        "status_failures": len(failures),
        "main_connected_ratio": (
            round(count_truthy([sample.get("main_connected") for sample in valid]) / len(valid), 4)
            if valid
            else None
        ),
        "main_max_frame_age_ms": maximum([sample.get("main_frame_age_ms") for sample in valid]),
        "main_frame_age_over_3000_count": count_truthy(
            [(sample.get("main_frame_age_ms") or 0) > 3000 for sample in valid]
        ),
        "main_restart_delta": restart_delta(valid, "main_restart_count"),
        "analysis_connected_ratio": (
            round(count_truthy([sample.get("analysis_connected") for sample in valid]) / len(valid), 4)
            if valid
            else None
        ),
        "analysis_max_frame_age_ms": maximum([sample.get("analysis_frame_age_ms") for sample in valid]),
        "analysis_frame_age_over_3000_count": count_truthy(
            [(sample.get("analysis_frame_age_ms") or 0) > 3000 for sample in valid]
        ),
        "analysis_restart_delta": restart_delta(valid, "analysis_restart_count"),
        "tracking_worker_fps_avg": average([sample.get("tracking_worker_fps") for sample in valid]),
        "tracking_worker_fps_min": minimum([sample.get("tracking_worker_fps") for sample in valid]),
        "result_publish_fps_avg": average([sample.get("result_publish_fps") for sample in valid]),
        "result_publish_fps_min": minimum([sample.get("result_publish_fps") for sample in valid]),
        "detection_worker_fps_avg": average([sample.get("detection_worker_fps") for sample in valid]),
        "pose_fps_avg": average([sample.get("pose_fps") for sample in valid]),
        "pose_latency_max_ms": maximum([sample.get("pose_latency_ms") for sample in valid]),
        "pose_skipped_due_to_busy_delta": restart_delta(valid, "pose_skipped_due_to_busy"),
        "pose_circuit_open_seen": any(bool(sample.get("pose_circuit_open")) for sample in valid),
        "pipeline_errors": count_truthy([sample.get("pipeline_last_error") for sample in valid]),
        "temporal_errors": count_truthy([sample.get("temporal_last_error") for sample in valid]),
        "gpu_util_avg": average([sample.get("gpu_util") for sample in samples]),
        "gpu_util_max": maximum([sample.get("gpu_util") for sample in samples]),
        "gpu_memory_mb_avg": average([sample.get("gpu_memory_mb") for sample in samples]),
        "gpu_memory_mb_max": maximum([sample.get("gpu_memory_mb") for sample in samples]),
        "webrtc_clients_max": maximum([sample.get("webrtc_clients") for sample in valid]),
        "ws_clients_max": maximum([sample.get("ws_clients") for sample in valid]),
        "vision_memory_delta_mb": None,
        "identity_memory_delta_mb": None,
    }

    if len(vision_memory) >= 2:
        summary["vision_memory_start_mb"] = vision_memory[0]
        summary["vision_memory_end_mb"] = vision_memory[-1]
        summary["vision_memory_delta_mb"] = round(vision_memory[-1] - vision_memory[0], 3)
    if len(identity_memory) >= 2:
        summary["identity_memory_start_mb"] = identity_memory[0]
        summary["identity_memory_end_mb"] = identity_memory[-1]
        summary["identity_memory_delta_mb"] = round(identity_memory[-1] - identity_memory[0], 3)

    return summary


def run(duration_sec: int, output_path: Path, label: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vision_pid = get_listener_pid(8000)
    identity_pid = get_listener_pid(8100)
    started = time.monotonic()
    samples: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    print(
        json.dumps(
            {
                "event": "phase5_15f_start",
                "label": label,
                "duration_sec": duration_sec,
                "vision_pid": vision_pid,
                "identity_pid": identity_pid,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    for index in range(duration_sec):
        tick = time.monotonic()
        sample: dict[str, Any] = {"i": index + 1, "at": now_iso()}
        try:
            status = get_status()
            main = status.get("main_stream") or {}
            analysis = status.get("analysis_stream") or {}
            pipeline = status.get("pipeline") or {}
            pose = status.get("pose") or {}
            temporal = status.get("temporal") or {}
            streaming = status.get("streaming") or {}
            detection = (status.get("detection") or [{}])[0]

            sample.update(
                {
                    "main_state": main.get("stream_state"),
                    "main_connected": bool(main.get("connected")),
                    "main_frame_age_ms": main.get("frame_age_ms"),
                    "main_capture_fps": main.get("capture_fps"),
                    "main_restart_count": main.get("restart_count"),
                    "main_last_error": main.get("last_error"),
                    "analysis_state": analysis.get("stream_state"),
                    "analysis_connected": bool(analysis.get("connected")),
                    "analysis_frame_age_ms": analysis.get("frame_age_ms"),
                    "analysis_capture_fps": analysis.get("capture_fps"),
                    "analysis_restart_count": analysis.get("restart_count"),
                    "analysis_last_error": analysis.get("last_error"),
                    "display_source": status.get("display_source"),
                    "analysis_source": status.get("analysis_source"),
                    "detection_worker_fps": pipeline.get("detection_worker_fps"),
                    "tracking_worker_fps": pipeline.get("tracking_worker_fps"),
                    "result_publish_fps": pipeline.get("result_publish_fps"),
                    "pipeline_last_error": pipeline.get("last_error"),
                    "detection_fps": detection.get("detection_fps"),
                    "pose_fps": pose.get("pose_fps"),
                    "pose_latency_ms": pose.get("last_inference_latency_ms"),
                    "pose_skipped_due_to_busy": pose.get("skipped_due_to_busy"),
                    "pose_circuit_open": pose.get("circuit_open"),
                    "temporal_last_error": temporal.get("last_error"),
                    "webrtc_clients": streaming.get("webrtc_clients"),
                    "ws_clients": streaming.get("ws_clients"),
                }
            )
        except Exception as exc:
            sample["status_error"] = repr(exc)
            failures.append({"i": index + 1, "at": sample["at"], "error": repr(exc)})

        if index % 5 == 0:
            sample.update(get_gpu())
            sample["vision_memory_mb"] = get_memory_mb(vision_pid)
            sample["identity_memory_mb"] = get_memory_mb(identity_pid)

        samples.append(sample)
        if (index + 1) % 60 == 0:
            print(
                json.dumps(
                    {
                        "event": "progress",
                        "label": label,
                        "minute": (index + 1) // 60,
                        "samples": len(samples),
                        "failures": len(failures),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

        elapsed = time.monotonic() - tick
        time.sleep(max(0, 1.0 - elapsed))

    summary = summarize(samples, failures, started)
    payload = {
        "phase": "5.15F",
        "test": label,
        "started_at": samples[0]["at"] if samples else None,
        "ended_at": now_iso(),
        "vision_pid": vision_pid,
        "identity_pid": identity_pid,
        "summary": summary,
        "failures": failures,
        "samples": samples,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "event": "phase5_15f_done",
                "label": label,
                "out": str(output_path),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-sec", type=int, default=900)
    parser.add_argument("--output", default="logs/runtime_debug/phase5_15f_dual_stream_long_run.json")
    parser.add_argument("--label", default="dual_stream_long_run")
    args = parser.parse_args()
    run(args.duration_sec, Path(args.output), args.label)


if __name__ == "__main__":
    main()
