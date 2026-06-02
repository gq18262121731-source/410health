from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
IDENTITY_DIR = ROOT / "identity_service"


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5.19D RTSP capture diagnose.")
    parser.add_argument("--duration-sec", type=int, default=180)
    parser.add_argument("--default-rtsp-url", default="rtsp://admin:410410410@192.168.8.254:10554/tcp/av0_1")
    parser.add_argument("--main-stream-url", default="rtsp://admin:410410410@192.168.8.254:10554/tcp/av0_0")
    parser.add_argument("--analysis-stream-url", default="rtsp://admin:410410410@192.168.8.254:10554/tcp/av0_1")
    parser.add_argument("--output-json", default=str(ROOT / "logs" / "runtime_debug" / "phase5_19d_rtsp_capture_diagnose.json"))
    parser.add_argument("--report-md", default=str(ROOT / "docs" / "phase5_19d_rtsp_capture_diagnose_report.md"))
    args = parser.parse_args()

    clear_ports([8000, 8100])
    identity = start_identity_service()
    vision = None
    try:
        wait_http("Identity Service", "http://127.0.0.1:8100/healthz", 60)
        vision = start_vision_service(
            build_vision_env(
                default_rtsp_url=args.default_rtsp_url,
                main_stream_url=args.main_stream_url,
                analysis_stream_url=args.analysis_stream_url,
            )
        )
        wait_http("Vision Service", "http://127.0.0.1:8000/healthz", 60)
        payload = collect_runtime(args.duration_sec)
        output_json = Path(args.output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(args.report_md).write_text(render_report(payload), encoding="utf-8")
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
        return 0
    finally:
        stop_process(vision)
        stop_process(identity)
        wait_for_port_down(8000, 20)
        wait_for_port_down(8100, 20)


def build_vision_env(*, default_rtsp_url: str, main_stream_url: str, analysis_stream_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "ENABLE_TRACKING": "true",
            "ENABLE_IDENTITY_BINDING": "true",
            "IDENTITY_BINDING_ASYNC": "true",
            "IDENTITY_SERVICE_URL": "http://127.0.0.1:8100",
            "IDENTITY_REQUEST_TIMEOUT_MS": "1000",
            "ENABLE_DUAL_STREAM": "true",
            "DEFAULT_RTSP_URL": default_rtsp_url,
            "MAIN_STREAM_URL": main_stream_url,
            "ANALYSIS_STREAM_URL": analysis_stream_url,
            "CAPTURE_BACKEND": "subprocess_opencv",
            "MAIN_CAPTURE_BACKEND": "subprocess_opencv",
            "ANALYSIS_CAPTURE_BACKEND": "subprocess_opencv",
            "CAPTURE_PROCESS_FRAME_TIMEOUT_MS": "2000",
            "CAPTURE_PROCESS_RESTART_MS": "500",
            "CAPTURE_JPEG_QUALITY": "60",
            "CAPTURE_PROCESS_OUTPUT_HEIGHT": "720",
            "CAPTURE_PROCESS_WRITE_FPS": "10",
            "MAIN_CAPTURE_JPEG_QUALITY": "55",
            "MAIN_CAPTURE_PROCESS_OUTPUT_HEIGHT": "720",
            "MAIN_CAPTURE_PROCESS_WRITE_FPS": "8",
            "YOLO_DEVICE": "cuda:0",
            "YOLO_IMGSZ": "416",
            "DETECTION_INTERVAL_MS": "100",
            "ENABLE_POSE": "true",
            "POSE_PROVIDER": "yolo",
            "POSE_WORKER_FPS": "5",
            "POSE_FPS": "5",
            "YOLO_POSE_IMGSZ": "320",
            "YOLO_POSE_DEVICE": "cuda:0",
            "POSE_SKIP_WHEN_INFERENCE_BUSY": "true",
            "POSE_TARGET_ONLY": "false",
            "POSE_FALLBACK_TO_LARGEST_TRACK": "true",
            "POSE_FALLBACK_TO_DETECTION": "true",
            "POSE_FALLBACK_MIN_CONFIDENCE": "0.35",
            "ENABLE_BEHAVIOR": "true",
            "ENABLE_TEMPORAL": "true",
            "TRACKING_WORKER_FPS": "12",
            "RESULT_PUBLISH_FPS": "10",
        }
    )
    return env


def collect_runtime(duration_sec: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    started = time.monotonic()
    for index in range(duration_sec):
        tick = time.monotonic()
        status = read_status()
        camera = (status.get("cameras") or [{}])[0]
        detection = (status.get("detection") or [{}])[0]
        tracking = status.get("tracking") or {}
        pose = status.get("pose") or {}
        pipeline = status.get("pipeline") or {}
        rows.append(
            {
                "i": index + 1,
                "at": utc_now_iso(),
                "camera_stream_state": camera.get("stream_state"),
                "camera_connected": camera.get("connected"),
                "camera_capture_fps": camera.get("capture_fps"),
                "camera_frame_age_ms": camera.get("frame_age_ms"),
                "camera_last_error": camera.get("last_error"),
                "camera_capture_process_last_error": camera.get("capture_process_last_error"),
                "camera_capture_process_last_exit_code": camera.get("capture_process_last_exit_code"),
                "main_stream_state": (status.get("main_stream") or {}).get("stream_state"),
                "analysis_stream_state": (status.get("analysis_stream") or {}).get("stream_state"),
                "analysis_frame_age_ms": (status.get("analysis_stream") or {}).get("frame_age_ms"),
                "detection_worker_fps": pipeline.get("detection_worker_fps"),
                "tracking_worker_fps": pipeline.get("tracking_worker_fps"),
                "result_publish_fps": pipeline.get("result_publish_fps"),
                "detection_latency_ms": detection.get("inference_latency_ms"),
                "tracking_objects_count": tracking.get("tracked_objects_count"),
                "target_track_id": tracking.get("tracked_target_id"),
                "target_exists": tracking.get("active_target_exists"),
                "pose_attempts": pose.get("pose_attempts"),
                "pose_success": pose.get("pose_success"),
                "pose_fps": pose.get("pose_fps"),
                "pose_skip_reasons": pose.get("pose_skip_reasons"),
                "pose_target_source": pose.get("pose_target_source"),
                "pose_objects_count": pose.get("pose_objects_count"),
                "pose_result_writeback_ok": pose.get("pose_result_writeback_ok"),
                "detection_objects_count": pose.get("detection_objects_count"),
                "tracking_objects_count_pose": pose.get("tracking_objects_count"),
                "target_objects_count": pose.get("target_objects_count"),
                "gpu": get_gpu(),
            }
        )
        elapsed = time.monotonic() - tick
        time.sleep(max(0, 1.0 - elapsed))

    summary = summarize(rows, time.monotonic() - started)
    return {
        "generated_at": utc_now_iso(),
        "duration_sec": duration_sec,
        "summary": summary,
        "rows": rows,
    }


def summarize(rows: list[dict[str, Any]], duration_sec: float) -> dict[str, Any]:
    def avg(key: str) -> float | None:
        values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
        return round(sum(values) / len(values), 3) if values else None

    def mx(key: str) -> float | None:
        values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
        return round(max(values), 3) if values else None

    return {
        "duration_sec": round(duration_sec, 2),
        "camera_connected_ratio": round(sum(1 for row in rows if row.get("camera_connected")) / len(rows), 4) if rows else 0,
        "camera_capture_fps_avg": avg("camera_capture_fps"),
        "camera_frame_age_max_ms": mx("camera_frame_age_ms"),
        "analysis_frame_age_max_ms": mx("analysis_frame_age_ms"),
        "detection_worker_fps_avg": avg("detection_worker_fps"),
        "tracking_worker_fps_avg": avg("tracking_worker_fps"),
        "result_publish_fps_avg": avg("result_publish_fps"),
        "detection_objects_count_max": mx("detection_objects_count"),
        "tracking_objects_count_max": mx("tracking_objects_count"),
        "target_objects_count_max": mx("target_objects_count"),
        "pose_attempts_last": rows[-1].get("pose_attempts") if rows else 0,
        "pose_success_last": rows[-1].get("pose_success") if rows else 0,
        "pose_skip_reasons_last": rows[-1].get("pose_skip_reasons") if rows else {},
        "pose_target_source_last": rows[-1].get("pose_target_source") if rows else None,
        "capture_process_errors_seen": sorted(
            {
                row.get("camera_capture_process_last_error")
                for row in rows
                if row.get("camera_capture_process_last_error")
            }
        ),
        "camera_errors_seen": sorted({row.get("camera_last_error") for row in rows if row.get("camera_last_error")}),
    }


def render_report(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Phase 5.19D RTSP Capture Diagnose Report",
        "",
        "This phase diagnoses RTSP capture stability before pose activation. It does not modify pose models, fall logic, Temporal, WebRTC architecture, or alerting.",
        "",
        "## Summary",
        "",
        f"- Camera connected ratio: `{summary.get('camera_connected_ratio')}`",
        f"- Camera capture_fps avg: `{summary.get('camera_capture_fps_avg')}`",
        f"- Camera frame_age max ms: `{summary.get('camera_frame_age_max_ms')}`",
        f"- Analysis frame_age max ms: `{summary.get('analysis_frame_age_max_ms')}`",
        f"- Detection worker FPS avg: `{summary.get('detection_worker_fps_avg')}`",
        f"- Tracking worker FPS avg: `{summary.get('tracking_worker_fps_avg')}`",
        f"- Publish FPS avg: `{summary.get('result_publish_fps_avg')}`",
        f"- Detection objects max: `{summary.get('detection_objects_count_max')}`",
        f"- Tracking objects max: `{summary.get('tracking_objects_count_max')}`",
        f"- Target objects max: `{summary.get('target_objects_count_max')}`",
        f"- Pose attempts last: `{summary.get('pose_attempts_last')}`",
        f"- Pose success last: `{summary.get('pose_success_last')}`",
        f"- Pose skip reasons last: `{summary.get('pose_skip_reasons_last')}`",
        f"- Pose target source last: `{summary.get('pose_target_source_last')}`",
        "",
        "## Capture Errors",
        "",
        f"- Capture process errors seen: `{summary.get('capture_process_errors_seen')}`",
        f"- Camera errors seen: `{summary.get('camera_errors_seen')}`",
        "",
        "## Artifact",
        "",
        f"- `{ROOT / 'logs' / 'runtime_debug' / 'phase5_19d_rtsp_capture_diagnose.json'}`",
    ]
    return "\n".join(lines) + "\n"


def read_status() -> dict[str, Any]:
    with urlopen("http://127.0.0.1:8000/status?camera_id=camera_01", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def get_gpu() -> dict[str, float | None]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {"util": None, "memory_mb": None}
        util, memory = [part.strip() for part in result.stdout.splitlines()[0].split(",")[:2]]
        return {"util": float(util), "memory_mb": float(memory)}
    except Exception:
        return {"util": None, "memory_mb": None}


def start_identity_service() -> subprocess.Popen:
    python_exe = r"C:\Users\13010\anaconda3\envs\identity310\python.exe"
    return subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8100"],
        cwd=str(IDENTITY_DIR),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )


def start_vision_service(env: dict[str, str]) -> subprocess.Popen:
    python_exe = r"C:\Users\13010\anaconda3\envs\torchgpu\python.exe"
    return subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(ROOT),
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )


def wait_http(name: str, url: str, timeout_sec: float) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except URLError:
            pass
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{name} did not respond within {timeout_sec:.0f}s: {url}")


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
        process.wait(timeout=10)
    except Exception:
        process.kill()
        process.wait(timeout=5)


def wait_for_port_down(port: int, timeout_sec: float) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not is_port_listening(port):
            return
        time.sleep(0.5)


def is_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def clear_ports(ports: list[int]) -> None:
    for port in ports:
        for pid in listener_pids(port):
            terminate_pid(pid)
        wait_for_port_down(port, 20)


def listener_pids(port: int) -> list[int]:
    result = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=10)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    pids: list[int] = []
    needle = f"127.0.0.1:{port}"
    for line in result.stdout.splitlines():
        text = line.strip()
        if not text or "LISTENING" not in text or needle not in text:
            continue
        parts = text.split()
        if len(parts) < 5:
            continue
        try:
            pids.append(int(parts[-1]))
        except ValueError:
            continue
    return sorted(set(pids))


def terminate_pid(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=15)
    except Exception:
        return


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
