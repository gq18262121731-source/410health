from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs" / "runtime_debug"
IDENTITY_DIR = ROOT / "identity_service"


@dataclass(frozen=True)
class Scenario:
    key: str
    pose_fps: int
    pose_worker_fps: int
    pose_target_only: bool


SCENARIOS = [
    Scenario(key="A_pose_1fps_baseline", pose_fps=1, pose_worker_fps=1, pose_target_only=False),
    Scenario(key="B_pose_2fps", pose_fps=2, pose_worker_fps=2, pose_target_only=False),
    Scenario(key="C_pose_5fps", pose_fps=5, pose_worker_fps=5, pose_target_only=False),
    Scenario(key="D_target_only_pose_5fps", pose_fps=5, pose_worker_fps=5, pose_target_only=True),
    Scenario(key="E_target_only_pose_10fps", pose_fps=10, pose_worker_fps=10, pose_target_only=True),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5.19 pose smoothness / quality matrix.")
    parser.add_argument("--duration-sec", type=int, default=180)
    parser.add_argument("--default-rtsp-url", default="rtsp://admin:410410410@192.168.8.254:10554/tcp/av0_1")
    parser.add_argument("--main-stream-url", default="rtsp://admin:410410410@192.168.8.254:10554/tcp/av0_0")
    parser.add_argument("--analysis-stream-url", default="rtsp://admin:410410410@192.168.8.254:10554/tcp/av0_1")
    parser.add_argument(
        "--output-json",
        default=str(LOG_DIR / "phase5_19_pose_quality.json"),
    )
    parser.add_argument(
        "--report-md",
        default=str(ROOT / "docs" / "phase5_19_pose_quality_report.md"),
    )
    args = parser.parse_args()

    clear_ports([8000, 8100])
    results = [
        run_scenario(
            scenario,
            args.duration_sec,
            default_rtsp_url=args.default_rtsp_url,
            main_stream_url=args.main_stream_url,
            analysis_stream_url=args.analysis_stream_url,
        )
        for scenario in SCENARIOS
    ]
    payload = {
        "phase": "5.19",
        "generated_at": utc_now_iso(),
        "duration_sec": args.duration_sec,
        "results": results,
        "recommendation": build_recommendation(results),
    }
    output_json = Path(args.output_json)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.report_md).write_text(render_report(payload), encoding="utf-8")
    print(json.dumps(payload["recommendation"], ensure_ascii=False, indent=2))
    return 0


def run_scenario(
    scenario: Scenario,
    duration_sec: int,
    *,
    default_rtsp_url: str,
    main_stream_url: str,
    analysis_stream_url: str,
) -> dict[str, Any]:
    identity_process: subprocess.Popen | None = None
    vision_process: subprocess.Popen | None = None
    sample_output = LOG_DIR / f"phase5_19_{scenario.key}.json"
    started_at = utc_now_iso()

    try:
        clear_ports([8000, 8100])
        identity_process = start_identity_service()
        wait_http("Identity Service", "http://127.0.0.1:8100/healthz", 60)

        vision_env = build_vision_env(
            scenario,
            default_rtsp_url=default_rtsp_url,
            main_stream_url=main_stream_url,
            analysis_stream_url=analysis_stream_url,
        )
        vision_process = start_vision_service(vision_env)
        wait_http("Vision Service", "http://127.0.0.1:8000/healthz", 60)

        sample_runtime(duration_sec, sample_output)
        sample_payload = json.loads(sample_output.read_text(encoding="utf-8"))
        summary = sample_payload.get("summary") or {}
        return {
            "scenario": scenario.key,
            "started_at": started_at,
            "ended_at": utc_now_iso(),
            "config": {
                "DEFAULT_RTSP_URL": default_rtsp_url,
                "MAIN_STREAM_URL": main_stream_url,
                "ANALYSIS_STREAM_URL": analysis_stream_url,
                "DETECTION_INTERVAL_MS": 100,
                "YOLO_IMGSZ": 416,
                "YOLO_DEVICE": "cuda:0",
                "POSE_FPS": scenario.pose_fps,
                "POSE_WORKER_FPS": scenario.pose_worker_fps,
                "YOLO_POSE_IMGSZ": 320,
                "YOLO_POSE_DEVICE": "cuda:0",
                "POSE_TARGET_ONLY": str(scenario.pose_target_only).lower(),
            },
            "summary": summary,
            "sample_log": str(sample_output),
        }
    finally:
        stop_process("Vision Service", vision_process)
        stop_process("Identity Service", identity_process)
        wait_for_port_down(8000, timeout_sec=20)
        wait_for_port_down(8100, timeout_sec=20)


def build_vision_env(
    scenario: Scenario,
    *,
    default_rtsp_url: str,
    main_stream_url: str,
    analysis_stream_url: str,
) -> dict[str, str]:
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
            "DISPLAY_FALLBACK_TO_ANALYSIS": "true",
            "DISPLAY_FALLBACK_FRAME_AGE_MS": "1500",
            "DISPLAY_FALLBACK_MIN_HOLD_MS": "10000",
            "DETECTION_ENABLED": "true",
            "YOLO_DEVICE": "cuda:0",
            "YOLO_IMGSZ": "416",
            "DETECTION_INTERVAL_MS": "100",
            "ENABLE_POSE": "true",
            "POSE_PROVIDER": "yolo",
            "POSE_WORKER_FPS": str(scenario.pose_worker_fps),
            "POSE_FPS": str(scenario.pose_fps),
            "YOLO_POSE_IMGSZ": "320",
            "YOLO_POSE_DEVICE": "cuda:0",
            "POSE_SKIP_WHEN_INFERENCE_BUSY": "true",
            "POSE_MAX_INFERENCE_MS": "1500",
            "POSE_SLOW_INFERENCE_CIRCUIT_BREAKER_COUNT": "3",
            "POSE_CIRCUIT_BREAKER_COOLDOWN_MS": "10000",
            "ENABLE_BEHAVIOR": "true",
            "ENABLE_TEMPORAL": "true",
            "TRACKING_WORKER_FPS": "12",
            "RESULT_PUBLISH_FPS": "10",
            "POSE_TARGET_ONLY": str(scenario.pose_target_only).lower(),
        }
    )
    return env


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


def sample_runtime(duration_sec: int, output_path: Path) -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "sample_phase5_19_runtime.py"),
        "--duration-sec",
        str(duration_sec),
        "--output",
        str(output_path),
    ]
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=duration_sec + 120)
    if result.returncode != 0:
        raise RuntimeError(f"pose runtime sampler failed: {result.stdout}\n{result.stderr}")


def build_recommendation(results: list[dict[str, Any]]) -> dict[str, Any]:
    scored = []
    for item in results:
        summary = item.get("summary") or {}
        score = 0
        if (summary.get("detection_worker_fps_avg") or 0) >= 8:
            score += 3
        if (summary.get("tracking_worker_fps_avg") or 0) >= 10:
            score += 2
        if (summary.get("result_publish_fps_avg") or 0) >= 9:
            score += 2
        if (summary.get("pose_fps_avg") or 0) >= 5:
            score += 3
        elif (summary.get("pose_fps_avg") or 0) >= 2:
            score += 1
        if (summary.get("main_frame_age_over_3000_count") or 0) == 0:
            score += 1
        if (summary.get("analysis_frame_age_over_3000_count") or 0) == 0:
            score += 1
        if (summary.get("pipeline_errors") or 0) == 0:
            score += 1
        scored.append((score, item))
    best = max(scored, key=lambda pair: pair[0])[1] if scored else None
    return {
        "recommended_scenario": best.get("scenario") if best else None,
        "recommended_config": best.get("config") if best else None,
        "reason": "Best balance of visible pose cadence, stable video, and preserved detect/tracking/publish throughput.",
    }


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 5.19 Pose Smoothness / Quality Report",
        "",
        "This phase compares pose cadence options and target-only pose behavior without changing fall logic, Temporal rules, or alerting.",
        "",
        "## Matrix",
        "",
        "| Scenario | Pose FPS Config | Target-only | Pose FPS Avg | Pose Latency Avg | Pose Latency P95 | Pose Latency Max | Pose Skipped Busy | Detect FPS Avg | Tracking FPS Avg | Publish FPS Avg | Main >3000ms | Analysis >3000ms | GPU Avg | CPU Avg |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in payload.get("results", []):
        summary = item.get("summary") or {}
        config = item.get("config") or {}
        lines.append(
            "| {scenario} | {pose_fps} | {target_only} | {pose_avg} | {pose_latency} | {pose_p95} | {pose_max} | {skipped} | {detect} | {tracking} | {publish} | {main_stale} | {analysis_stale} | {gpu_avg} | {cpu_avg} |".format(
                scenario=item.get("scenario"),
                pose_fps=config.get("POSE_FPS"),
                target_only=config.get("POSE_TARGET_ONLY"),
                pose_avg=summary.get("pose_fps_avg"),
                pose_latency=summary.get("pose_latency_avg_ms"),
                pose_p95=summary.get("pose_latency_p95_ms"),
                pose_max=summary.get("pose_latency_max_ms"),
                skipped=summary.get("pose_skipped_due_to_busy_delta"),
                detect=summary.get("detection_worker_fps_avg"),
                tracking=summary.get("tracking_worker_fps_avg"),
                publish=summary.get("result_publish_fps_avg"),
                main_stale=summary.get("main_frame_age_over_3000_count"),
                analysis_stale=summary.get("analysis_frame_age_over_3000_count"),
                gpu_avg=summary.get("gpu_util_avg"),
                cpu_avg=summary.get("cpu_util_approx_process_percent"),
            )
        )

    recommendation = payload.get("recommendation") or {}
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- Recommended scenario: `{recommendation.get('recommended_scenario')}`",
            f"- Recommended config: `{recommendation.get('recommended_config')}`",
            "",
            "## Notes",
            "",
            "- Current backend already uses target-preferred pose selection inside `PoseService`.",
            "- Frontend smoothing/interpolation can make low backend pose FPS look less jerky without blocking detect.",
            "- If pose >= 5 FPS is still not stable in full pipeline mode, target-only pose remains the next practical step.",
            "",
            "## Artifacts",
            "",
            f"- `{ROOT / 'logs' / 'runtime_debug' / 'phase5_19_pose_quality.json'}`",
            f"- `{ROOT / 'docs' / 'phase5_19_pose_quality_report.md'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def stop_process(name: str, process: subprocess.Popen | None) -> None:
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
        wait_for_port_down(port, timeout_sec=20)


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
