from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai.inference_guard import ultralytics_inference_lock
from app.core.config import Settings


DEFAULT_VIDEO_PATH = ROOT / "tests" / "fixtures" / "person_bus_loop.mp4"
DEFAULT_OUTPUT_JSON = ROOT / "logs" / "runtime_debug" / "phase5_17_ai_throughput_benchmark.json"
DEFAULT_IMGSZS = (640, 512, 416, 320)
DEFAULT_HALVES = (False, True)
DEFAULT_MEASURE_FRAMES = 40
DEFAULT_WARMUP_FRAMES = 10
DEFAULT_GPU_SAMPLE_INTERVAL_SEC = 0.2
DEFAULT_POSE_LOW_FREQ_EVERY_N = 5


@dataclass(frozen=True)
class SourceSpec:
    mode: str
    video_path: str | None
    rtsp_url: str | None
    warmup_width: int
    warmup_height: int
    preload_frames: int


class GPUSampler:
    def __init__(self, interval_sec: float) -> None:
        self.interval_sec = max(interval_sec, 0.05)
        self.samples: list[dict[str, float | None]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="gpu-sampler", daemon=True)

    def __enter__(self) -> "GPUSampler":
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            snapshot = query_gpu_snapshot()
            if snapshot:
                self.samples.append(snapshot)
            self._stop.wait(self.interval_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 5.17 AI throughput benchmark.")
    parser.add_argument("--source", choices=("video", "rtsp", "warmup"), default="video")
    parser.add_argument("--video-path", default=str(DEFAULT_VIDEO_PATH))
    parser.add_argument("--rtsp-url", default=None)
    parser.add_argument("--warmup-width", type=int, default=1280)
    parser.add_argument("--warmup-height", type=int, default=720)
    parser.add_argument("--measure-frames", type=int, default=DEFAULT_MEASURE_FRAMES)
    parser.add_argument("--warmup-frames", type=int, default=DEFAULT_WARMUP_FRAMES)
    parser.add_argument("--preload-frames", type=int, default=90)
    parser.add_argument("--gpu-sample-interval-sec", type=float, default=DEFAULT_GPU_SAMPLE_INTERVAL_SEC)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--pose-low-freq-every-n", type=int, default=DEFAULT_POSE_LOW_FREQ_EVERY_N)
    parser.add_argument("--lock-detect-interval-ms", type=int, default=200)
    parser.add_argument("--lock-pose-worker-fps", type=float, default=2.0)
    parser.add_argument("--lock-pose-imgsz", type=int, default=320)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    assert_cuda_ready(args.device)

    source = SourceSpec(
        mode=args.source,
        video_path=args.video_path,
        rtsp_url=args.rtsp_url,
        warmup_width=args.warmup_width,
        warmup_height=args.warmup_height,
        preload_frames=max(args.preload_frames, args.measure_frames + args.warmup_frames),
    )
    frames, source_meta = load_frames(source)

    online_status = read_online_status()
    settings = Settings()

    report: dict[str, Any] = {
        "generated_at": utc_timestamp(),
        "system": collect_system_snapshot(args.device),
        "source": source_meta,
        "benchmark_args": {
            "measure_frames": args.measure_frames,
            "warmup_frames": args.warmup_frames,
            "gpu_sample_interval_sec": args.gpu_sample_interval_sec,
            "device": args.device,
            "pose_low_freq_every_n": args.pose_low_freq_every_n,
            "lock_detect_interval_ms": args.lock_detect_interval_ms,
            "lock_pose_worker_fps": args.lock_pose_worker_fps,
            "lock_pose_imgsz": args.lock_pose_imgsz,
        },
        "online_status_snapshot": online_status,
        "service_config_snapshot": {
            "detection_interval_ms": settings.detection_interval_ms,
            "detection_worker_cap_fps": round(1000.0 / settings.detection_interval_ms, 2)
            if settings.detection_interval_ms > 0
            else None,
            "pose_fps": settings.pose_fps,
            "pose_worker_fps": settings.pose_worker_fps,
            "pose_skip_when_inference_busy": settings.pose_skip_when_inference_busy,
        },
        "runs": [],
    }

    detect_runs = benchmark_detect_only(
        frames=frames,
        device=args.device,
        measure_frames=args.measure_frames,
        warmup_frames=args.warmup_frames,
        gpu_sample_interval_sec=args.gpu_sample_interval_sec,
    )
    report["runs"].extend(detect_runs)

    pose_runs = benchmark_pose_only(
        frames=frames,
        device=args.device,
        measure_frames=args.measure_frames,
        warmup_frames=args.warmup_frames,
        gpu_sample_interval_sec=args.gpu_sample_interval_sec,
    )
    report["runs"].extend(pose_runs)

    sequential_runs = benchmark_detect_pose_sequential(
        frames=frames,
        device=args.device,
        measure_frames=args.measure_frames,
        warmup_frames=args.warmup_frames,
        gpu_sample_interval_sec=args.gpu_sample_interval_sec,
    )
    report["runs"].extend(sequential_runs)

    lock_runs = benchmark_detect_pose_lock_simulation(
        frames=frames,
        device=args.device,
        measure_frames=args.measure_frames,
        warmup_frames=args.warmup_frames,
        gpu_sample_interval_sec=args.gpu_sample_interval_sec,
        detect_interval_ms=args.lock_detect_interval_ms,
        pose_worker_fps=args.lock_pose_worker_fps,
        pose_imgsz=args.lock_pose_imgsz,
    )
    report["runs"].extend(lock_runs)

    target_pose_runs = benchmark_target_pose_strategies(
        frames=frames,
        device=args.device,
        measure_frames=args.measure_frames,
        warmup_frames=args.warmup_frames,
        gpu_sample_interval_sec=args.gpu_sample_interval_sec,
        pose_every_n=args.pose_low_freq_every_n,
    )
    report["runs"].extend(target_pose_runs)

    report["summary"] = build_summary(report["runs"], report["online_status_snapshot"], report["service_config_snapshot"])
    write_json(Path(args.output_json), report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


def benchmark_detect_only(
    frames: list[np.ndarray],
    device: str,
    measure_frames: int,
    warmup_frames: int,
    gpu_sample_interval_sec: float,
) -> list[dict[str, Any]]:
    from ultralytics import YOLO

    runs: list[dict[str, Any]] = []
    for imgsz in DEFAULT_IMGSZS:
        for half in DEFAULT_HALVES:
            model = YOLO("yolov8n.pt")
            kwargs = build_detect_kwargs(device=device, imgsz=imgsz, half=half)
            prewarm_predict(model, frames, kwargs, warmup_frames)
            with GPUSampler(gpu_sample_interval_sec) as sampler:
                latencies, wall_sec, _, _ = run_predict_loop(model, frames, kwargs, measure_frames)
            runs.append(
                make_base_run(
                    phase="A",
                    category="detect_only",
                    scenario=f"detect_yolov8n_{imgsz}_{'fp16' if half else 'fp32'}",
                    input_frames=measure_frames,
                    input_shape=shape_of(frames[0]),
                    wall_sec=wall_sec,
                    latencies_ms=latencies,
                    gpu_samples=sampler.samples,
                    extra={
                        "model_path": "yolov8n.pt",
                        "imgsz": imgsz,
                        "half": half,
                        "device": device,
                        "predictor_device": predictor_device(model),
                        "result_kind": "boxes",
                    },
                )
            )
            release_model(model)
    return runs


def benchmark_pose_only(
    frames: list[np.ndarray],
    device: str,
    measure_frames: int,
    warmup_frames: int,
    gpu_sample_interval_sec: float,
) -> list[dict[str, Any]]:
    from ultralytics import YOLO

    runs: list[dict[str, Any]] = []
    for imgsz in DEFAULT_IMGSZS:
        for half in DEFAULT_HALVES:
            model = YOLO("yolov8n-pose.pt")
            kwargs = build_pose_kwargs(device=device, imgsz=imgsz, half=half)
            prewarm_predict(model, frames, kwargs, warmup_frames)
            with GPUSampler(gpu_sample_interval_sec) as sampler:
                latencies, wall_sec, _, _ = run_predict_loop(model, frames, kwargs, measure_frames)
            runs.append(
                make_base_run(
                    phase="B",
                    category="pose_only",
                    scenario=f"pose_yolov8n_pose_{imgsz}_{'fp16' if half else 'fp32'}",
                    input_frames=measure_frames,
                    input_shape=shape_of(frames[0]),
                    wall_sec=wall_sec,
                    latencies_ms=latencies,
                    gpu_samples=sampler.samples,
                    extra={
                        "model_path": "yolov8n-pose.pt",
                        "imgsz": imgsz,
                        "half": half,
                        "device": device,
                        "predictor_device": predictor_device(model),
                        "result_kind": "pose",
                    },
                )
            )
            release_model(model)
    return runs


def benchmark_detect_pose_sequential(
    frames: list[np.ndarray],
    device: str,
    measure_frames: int,
    warmup_frames: int,
    gpu_sample_interval_sec: float,
) -> list[dict[str, Any]]:
    from ultralytics import YOLO

    runs: list[dict[str, Any]] = []
    for imgsz in DEFAULT_IMGSZS:
        for half in DEFAULT_HALVES:
            detect_model = YOLO("yolov8n.pt")
            pose_model = YOLO("yolov8n-pose.pt")
            detect_kwargs = build_detect_kwargs(device=device, imgsz=imgsz, half=half)
            pose_kwargs = build_pose_kwargs(device=device, imgsz=imgsz, half=half)

            for frame in iter_frames(frames, warmup_frames):
                infer_once(detect_model, frame, detect_kwargs)
                infer_once(pose_model, frame, pose_kwargs)

            total_latencies: list[float] = []
            detect_latencies: list[float] = []
            pose_latencies: list[float] = []
            started = time.perf_counter()
            with GPUSampler(gpu_sample_interval_sec) as sampler:
                for frame in iter_frames(frames, measure_frames):
                    detect_latency, _ = infer_once(detect_model, frame, detect_kwargs)
                    pose_latency, _ = infer_once(pose_model, frame, pose_kwargs)
                    detect_latencies.append(detect_latency)
                    pose_latencies.append(pose_latency)
                    total_latencies.append(detect_latency + pose_latency)
            wall_sec = time.perf_counter() - started

            runs.append(
                make_base_run(
                    phase="C",
                    category="detect_pose_sequential",
                    scenario=f"detect_pose_seq_{imgsz}_{'fp16' if half else 'fp32'}",
                    input_frames=measure_frames,
                    input_shape=shape_of(frames[0]),
                    wall_sec=wall_sec,
                    latencies_ms=total_latencies,
                    gpu_samples=sampler.samples,
                    extra={
                        "detect_model_path": "yolov8n.pt",
                        "pose_model_path": "yolov8n-pose.pt",
                        "detect_imgsz": imgsz,
                        "pose_imgsz": imgsz,
                        "half": half,
                        "device": device,
                        "detect_predictor_device": predictor_device(detect_model),
                        "pose_predictor_device": predictor_device(pose_model),
                        "detect_latency_avg_ms": round(mean(detect_latencies), 2),
                        "detect_latency_p95_ms": round(percentile(detect_latencies, 95), 2),
                        "pose_latency_avg_ms": round(mean(pose_latencies), 2),
                        "pose_latency_p95_ms": round(percentile(pose_latencies, 95), 2),
                    },
                )
            )
            release_model(detect_model)
            release_model(pose_model)
    return runs


def benchmark_detect_pose_lock_simulation(
    frames: list[np.ndarray],
    device: str,
    measure_frames: int,
    warmup_frames: int,
    gpu_sample_interval_sec: float,
    detect_interval_ms: int,
    pose_worker_fps: float,
    pose_imgsz: int,
) -> list[dict[str, Any]]:
    configs = [
        {"name": "service_baseline_fp32", "detect_imgsz": 640, "pose_imgsz": pose_imgsz, "half": False},
        {"name": "service_baseline_fp16", "detect_imgsz": 640, "pose_imgsz": pose_imgsz, "half": True},
        {"name": "service_tuned_fp16", "detect_imgsz": 416, "pose_imgsz": 320, "half": True},
    ]
    return [
        run_lock_simulation(
            frames=frames,
            device=device,
            measure_frames=measure_frames,
            warmup_frames=warmup_frames,
            gpu_sample_interval_sec=gpu_sample_interval_sec,
            detect_interval_ms=detect_interval_ms,
            pose_worker_fps=pose_worker_fps,
            detect_imgsz=item["detect_imgsz"],
            pose_imgsz=item["pose_imgsz"],
            half=item["half"],
            scenario_name=item["name"],
        )
        for item in configs
    ]


def benchmark_target_pose_strategies(
    frames: list[np.ndarray],
    device: str,
    measure_frames: int,
    warmup_frames: int,
    gpu_sample_interval_sec: float,
    pose_every_n: int,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    target_configs = [
        {"detect_imgsz": 640, "pose_imgsz": 320, "half": False},
        {"detect_imgsz": 640, "pose_imgsz": 320, "half": True},
        {"detect_imgsz": 416, "pose_imgsz": 320, "half": False},
        {"detect_imgsz": 416, "pose_imgsz": 320, "half": True},
    ]
    for config in target_configs:
        runs.append(
            run_target_crop_pose_sequential(
                frames=frames,
                device=device,
                measure_frames=measure_frames,
                warmup_frames=warmup_frames,
                gpu_sample_interval_sec=gpu_sample_interval_sec,
                detect_imgsz=config["detect_imgsz"],
                pose_imgsz=config["pose_imgsz"],
                half=config["half"],
            )
        )
    for half in DEFAULT_HALVES:
        runs.append(
            run_low_frequency_full_frame_pose(
                frames=frames,
                device=device,
                measure_frames=measure_frames,
                warmup_frames=warmup_frames,
                gpu_sample_interval_sec=gpu_sample_interval_sec,
                detect_imgsz=640,
                pose_imgsz=320,
                half=half,
                pose_every_n=pose_every_n,
            )
        )
    return runs


def run_lock_simulation(
    frames: list[np.ndarray],
    device: str,
    measure_frames: int,
    warmup_frames: int,
    gpu_sample_interval_sec: float,
    detect_interval_ms: int,
    pose_worker_fps: float,
    detect_imgsz: int,
    pose_imgsz: int,
    half: bool,
    scenario_name: str,
) -> dict[str, Any]:
    from ultralytics import YOLO

    detect_model = YOLO("yolov8n.pt")
    pose_model = YOLO("yolov8n-pose.pt")
    detect_kwargs = build_detect_kwargs(device=device, imgsz=detect_imgsz, half=half)
    pose_kwargs = build_pose_kwargs(device=device, imgsz=pose_imgsz, half=half)

    # Warm models and make sure the crop path has seen at least one target.
    for frame in iter_frames(frames, warmup_frames):
        _, result = infer_once(detect_model, frame, detect_kwargs)
        crop = extract_largest_person_crop(frame, result)
        if crop is not None:
            infer_once(pose_model, crop, pose_kwargs)

    latest_state: dict[str, Any] = {"frame": None, "crop": None}
    state_lock = threading.Lock()
    detection_latencies: list[float] = []
    pose_latencies: list[float] = []
    pose_skipped_due_to_busy = 0
    pose_no_target = 0
    detect_count = 0
    pose_count = 0
    detect_index = 0
    detect_done = threading.Event()

    detect_interval_sec = max(detect_interval_ms / 1000.0, 0.001)
    pose_interval_sec = 1.0 / max(pose_worker_fps, 0.1)

    def detect_worker() -> None:
        nonlocal detect_count, detect_index
        next_tick = time.perf_counter()
        for _ in range(measure_frames):
            sleep_until(next_tick)
            frame = frames[detect_index % len(frames)]
            detect_index += 1
            with ultralytics_inference_lock(blocking=True):
                latency_ms, result = infer_once(detect_model, frame, detect_kwargs)
            detection_latencies.append(latency_ms)
            crop = extract_largest_person_crop(frame, result)
            with state_lock:
                latest_state["frame"] = frame
                latest_state["crop"] = crop
            detect_count += 1
            next_tick += detect_interval_sec
        detect_done.set()

    def pose_worker() -> None:
        nonlocal pose_count, pose_skipped_due_to_busy, pose_no_target
        next_tick = time.perf_counter()
        while not detect_done.is_set():
            sleep_until(next_tick)
            with state_lock:
                crop = latest_state.get("crop")
            if crop is None:
                pose_no_target += 1
                next_tick += pose_interval_sec
                continue
            with ultralytics_inference_lock(blocking=False) as acquired:
                if not acquired:
                    pose_skipped_due_to_busy += 1
                else:
                    latency_ms, _ = infer_once(pose_model, crop, pose_kwargs)
                    pose_latencies.append(latency_ms)
                    pose_count += 1
            next_tick += pose_interval_sec

    started = time.perf_counter()
    with GPUSampler(gpu_sample_interval_sec) as sampler:
        detect_thread = threading.Thread(target=detect_worker, name="bench-detect", daemon=True)
        pose_thread = threading.Thread(target=pose_worker, name="bench-pose", daemon=True)
        detect_thread.start()
        pose_thread.start()
        detect_thread.join()
        pose_thread.join(timeout=2)
    wall_sec = time.perf_counter() - started

    run = make_base_run(
        phase="D",
        category="detect_pose_with_inference_lock",
        scenario=f"detect_pose_lock_{scenario_name}",
        input_frames=measure_frames,
        input_shape=shape_of(frames[0]),
        wall_sec=wall_sec,
        latencies_ms=detection_latencies,
        gpu_samples=sampler.samples,
        extra={
            "detect_model_path": "yolov8n.pt",
            "pose_model_path": "yolov8n-pose.pt",
            "detect_imgsz": detect_imgsz,
            "pose_imgsz": pose_imgsz,
            "half": half,
            "device": device,
            "detect_interval_ms": detect_interval_ms,
            "pose_worker_fps": pose_worker_fps,
            "detection_fps": round(detect_count / wall_sec, 2) if wall_sec > 0 else 0.0,
            "pose_fps": round(pose_count / wall_sec, 2) if wall_sec > 0 else 0.0,
            "pose_skipped_due_to_busy": pose_skipped_due_to_busy,
            "pose_no_target_ticks": pose_no_target,
            "pose_latency_avg_ms": round(mean(pose_latencies), 2) if pose_latencies else None,
            "pose_latency_p95_ms": round(percentile(pose_latencies, 95), 2) if pose_latencies else None,
            "pose_inference_count": pose_count,
            "detect_predictor_device": predictor_device(detect_model),
            "pose_predictor_device": predictor_device(pose_model),
        },
    )
    release_model(detect_model)
    release_model(pose_model)
    return run


def run_target_crop_pose_sequential(
    frames: list[np.ndarray],
    device: str,
    measure_frames: int,
    warmup_frames: int,
    gpu_sample_interval_sec: float,
    detect_imgsz: int,
    pose_imgsz: int,
    half: bool,
) -> dict[str, Any]:
    from ultralytics import YOLO

    detect_model = YOLO("yolov8n.pt")
    pose_model = YOLO("yolov8n-pose.pt")
    detect_kwargs = build_detect_kwargs(device=device, imgsz=detect_imgsz, half=half)
    pose_kwargs = build_pose_kwargs(device=device, imgsz=pose_imgsz, half=half)

    for frame in iter_frames(frames, warmup_frames):
        _, detect_result = infer_once(detect_model, frame, detect_kwargs)
        crop = extract_largest_person_crop(frame, detect_result)
        if crop is not None:
            infer_once(pose_model, crop, pose_kwargs)

    total_latencies: list[float] = []
    detect_latencies: list[float] = []
    pose_latencies: list[float] = []
    pose_invocations = 0

    started = time.perf_counter()
    with GPUSampler(gpu_sample_interval_sec) as sampler:
        for frame in iter_frames(frames, measure_frames):
            detect_latency, detect_result = infer_once(detect_model, frame, detect_kwargs)
            detect_latencies.append(detect_latency)
            total_ms = detect_latency
            crop = extract_largest_person_crop(frame, detect_result)
            if crop is not None:
                pose_latency, _ = infer_once(pose_model, crop, pose_kwargs)
                pose_latencies.append(pose_latency)
                total_ms += pose_latency
                pose_invocations += 1
            total_latencies.append(total_ms)
    wall_sec = time.perf_counter() - started

    run = make_base_run(
        phase="E",
        category="target_only_pose_crop",
        scenario=f"target_crop_pose_detect{detect_imgsz}_pose{pose_imgsz}_{'fp16' if half else 'fp32'}",
        input_frames=measure_frames,
        input_shape=shape_of(frames[0]),
        wall_sec=wall_sec,
        latencies_ms=total_latencies,
        gpu_samples=sampler.samples,
        extra={
            "detect_model_path": "yolov8n.pt",
            "pose_model_path": "yolov8n-pose.pt",
            "detect_imgsz": detect_imgsz,
            "pose_imgsz": pose_imgsz,
            "half": half,
            "device": device,
            "pose_invocations": pose_invocations,
            "pose_invocation_ratio": round(pose_invocations / measure_frames, 4) if measure_frames else 0.0,
            "detect_latency_avg_ms": round(mean(detect_latencies), 2),
            "pose_latency_avg_ms": round(mean(pose_latencies), 2) if pose_latencies else None,
            "detect_predictor_device": predictor_device(detect_model),
            "pose_predictor_device": predictor_device(pose_model),
        },
    )
    release_model(detect_model)
    release_model(pose_model)
    return run


def run_low_frequency_full_frame_pose(
    frames: list[np.ndarray],
    device: str,
    measure_frames: int,
    warmup_frames: int,
    gpu_sample_interval_sec: float,
    detect_imgsz: int,
    pose_imgsz: int,
    half: bool,
    pose_every_n: int,
) -> dict[str, Any]:
    from ultralytics import YOLO

    detect_model = YOLO("yolov8n.pt")
    pose_model = YOLO("yolov8n-pose.pt")
    detect_kwargs = build_detect_kwargs(device=device, imgsz=detect_imgsz, half=half)
    pose_kwargs = build_pose_kwargs(device=device, imgsz=pose_imgsz, half=half)

    for frame in iter_frames(frames, warmup_frames):
        infer_once(detect_model, frame, detect_kwargs)
        if (warmup_frames > 0) and (warmup_frames % max(pose_every_n, 1) == 0):
            infer_once(pose_model, frame, pose_kwargs)

    total_latencies: list[float] = []
    detect_latencies: list[float] = []
    pose_latencies: list[float] = []
    pose_invocations = 0

    started = time.perf_counter()
    with GPUSampler(gpu_sample_interval_sec) as sampler:
        for index, frame in enumerate(iter_frames(frames, measure_frames)):
            detect_latency, _ = infer_once(detect_model, frame, detect_kwargs)
            detect_latencies.append(detect_latency)
            total_ms = detect_latency
            if index % max(pose_every_n, 1) == 0:
                pose_latency, _ = infer_once(pose_model, frame, pose_kwargs)
                pose_latencies.append(pose_latency)
                total_ms += pose_latency
                pose_invocations += 1
            total_latencies.append(total_ms)
    wall_sec = time.perf_counter() - started

    run = make_base_run(
        phase="E",
        category="full_frame_pose_low_frequency",
        scenario=f"low_freq_full_pose_detect{detect_imgsz}_pose{pose_imgsz}_{'fp16' if half else 'fp32'}",
        input_frames=measure_frames,
        input_shape=shape_of(frames[0]),
        wall_sec=wall_sec,
        latencies_ms=total_latencies,
        gpu_samples=sampler.samples,
        extra={
            "detect_model_path": "yolov8n.pt",
            "pose_model_path": "yolov8n-pose.pt",
            "detect_imgsz": detect_imgsz,
            "pose_imgsz": pose_imgsz,
            "half": half,
            "device": device,
            "pose_every_n_frames": pose_every_n,
            "pose_invocations": pose_invocations,
            "pose_invocation_ratio": round(pose_invocations / measure_frames, 4) if measure_frames else 0.0,
            "detect_latency_avg_ms": round(mean(detect_latencies), 2),
            "pose_latency_avg_ms": round(mean(pose_latencies), 2) if pose_latencies else None,
            "detect_predictor_device": predictor_device(detect_model),
            "pose_predictor_device": predictor_device(pose_model),
        },
    )
    release_model(detect_model)
    release_model(pose_model)
    return run


def run_predict_loop(model, frames: list[np.ndarray], kwargs: dict[str, Any], measure_frames: int) -> tuple[list[float], float, int, int]:
    latencies: list[float] = []
    inference_count = 0
    started = time.perf_counter()
    for frame in iter_frames(frames, measure_frames):
        latency_ms, _ = infer_once(model, frame, kwargs)
        latencies.append(latency_ms)
        inference_count += 1
    wall_sec = time.perf_counter() - started
    return latencies, wall_sec, inference_count, measure_frames


def prewarm_predict(model, frames: list[np.ndarray], kwargs: dict[str, Any], warmup_frames: int) -> None:
    for frame in iter_frames(frames, warmup_frames):
        infer_once(model, frame, kwargs)


def infer_once(model, frame: np.ndarray, kwargs: dict[str, Any]) -> tuple[float, Any]:
    sync_cuda()
    started = time.perf_counter()
    result = model.predict(frame, **kwargs)
    sync_cuda()
    return (time.perf_counter() - started) * 1000, result


def build_detect_kwargs(device: str, imgsz: int, half: bool) -> dict[str, Any]:
    return {
        "device": device,
        "imgsz": imgsz,
        "half": half,
        "conf": 0.35,
        "classes": [0],
        "verbose": False,
    }


def build_pose_kwargs(device: str, imgsz: int, half: bool) -> dict[str, Any]:
    return {
        "device": device,
        "imgsz": imgsz,
        "half": half,
        "conf": 0.25,
        "verbose": False,
    }


def extract_largest_person_crop(frame: np.ndarray, result: Any, padding_ratio: float = 0.08) -> np.ndarray | None:
    if not result:
        return None
    first = result[0]
    boxes = getattr(first, "boxes", None)
    if boxes is None:
        return None
    candidates: list[list[float]] = []
    for box in boxes:
        xyxy = box.xyxy[0].tolist()
        candidates.append([float(value) for value in xyxy])
    if not candidates:
        return None
    x1, y1, x2, y2 = max(candidates, key=bbox_area)
    height, width = frame.shape[:2]
    pad_x = (x2 - x1) * padding_ratio
    pad_y = (y2 - y1) * padding_ratio
    left = max(0, int(x1 - pad_x))
    top = max(0, int(y1 - pad_y))
    right = min(width, int(x2 + pad_x))
    bottom = min(height, int(y2 + pad_y))
    if right <= left or bottom <= top:
        return None
    crop = frame[top:bottom, left:right]
    return crop.copy() if crop.size else None


def load_frames(source: SourceSpec) -> tuple[list[np.ndarray], dict[str, Any]]:
    if source.mode == "warmup":
        rng = np.random.default_rng(20260526)
        frames = [
            rng.integers(0, 255, size=(source.warmup_height, source.warmup_width, 3), dtype=np.uint8)
            for _ in range(source.preload_frames)
        ]
        return frames, {
            "mode": "warmup",
            "description": "synthetic random frames",
            "frame_count": len(frames),
            "frame_width": source.warmup_width,
            "frame_height": source.warmup_height,
        }

    capture_target = source.rtsp_url if source.mode == "rtsp" else source.video_path
    if not capture_target:
        raise RuntimeError(f"missing capture target for source mode: {source.mode}")

    cap = cv2.VideoCapture(capture_target)
    if not cap.isOpened():
        raise RuntimeError(f"could not open source: {capture_target}")

    frames: list[np.ndarray] = []
    fps = cap.get(cv2.CAP_PROP_FPS) or None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    try:
        while len(frames) < source.preload_frames:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame.copy())
    finally:
        cap.release()

    if not frames:
        raise RuntimeError(f"source produced no frames: {capture_target}")

    if len(frames) < source.preload_frames:
        frames = extend_frames(frames, source.preload_frames)

    return frames, {
        "mode": source.mode,
        "description": str(capture_target),
        "frame_count": len(frames),
        "frame_width": width or frames[0].shape[1],
        "frame_height": height or frames[0].shape[0],
        "source_fps": fps,
        "source_frame_count": frame_count,
    }


def extend_frames(frames: list[np.ndarray], target_count: int) -> list[np.ndarray]:
    if not frames:
        return frames
    extended = list(frames)
    index = 0
    while len(extended) < target_count:
        extended.append(frames[index % len(frames)].copy())
        index += 1
    return extended


def iter_frames(frames: list[np.ndarray], count: int):
    for index in range(count):
        yield frames[index % len(frames)]


def make_base_run(
    phase: str,
    category: str,
    scenario: str,
    input_frames: int,
    input_shape: dict[str, int],
    wall_sec: float,
    latencies_ms: list[float],
    gpu_samples: list[dict[str, float | None]],
    extra: dict[str, Any],
) -> dict[str, Any]:
    avg_latency_ms = round(mean(latencies_ms), 2) if latencies_ms else None
    p95_latency_ms = round(percentile(latencies_ms, 95), 2) if latencies_ms else None
    run = {
        "phase": phase,
        "category": category,
        "scenario": scenario,
        "input_frames": input_frames,
        "input_shape": input_shape,
        "wall_sec": round(wall_sec, 4),
        "fps": round(input_frames / wall_sec, 2) if wall_sec > 0 else 0.0,
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "min_latency_ms": round(min(latencies_ms), 2) if latencies_ms else None,
        "max_latency_ms": round(max(latencies_ms), 2) if latencies_ms else None,
        "gpu": summarize_gpu_samples(gpu_samples),
    }
    run.update(extra)
    return run


def summarize_gpu_samples(samples: list[dict[str, float | None]]) -> dict[str, Any]:
    gpu_util = numeric_values(samples, "gpu_util_percent")
    gpu_mem = numeric_values(samples, "gpu_memory_used_mb")
    gpu_power = numeric_values(samples, "gpu_power_w")
    gpu_temp = numeric_values(samples, "gpu_temp_c")
    return {
        "samples": len(samples),
        "gpu_util_avg_percent": round(mean(gpu_util), 2) if gpu_util else None,
        "gpu_util_p95_percent": round(percentile(gpu_util, 95), 2) if gpu_util else None,
        "gpu_util_max_percent": round(max(gpu_util), 2) if gpu_util else None,
        "gpu_memory_avg_mb": round(mean(gpu_mem), 2) if gpu_mem else None,
        "gpu_memory_max_mb": round(max(gpu_mem), 2) if gpu_mem else None,
        "gpu_power_avg_w": round(mean(gpu_power), 2) if gpu_power else None,
        "gpu_temp_max_c": round(max(gpu_temp), 2) if gpu_temp else None,
    }


def numeric_values(items: list[dict[str, float | None]], key: str) -> list[float]:
    values: list[float] = []
    for item in items:
        value = item.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * (q / 100.0)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    weight = position - lower
    return lower_value + (upper_value - lower_value) * weight


def query_gpu_snapshot() -> dict[str, float | None] | None:
    command = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=3)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        util, mem_used, temp, power = [part.strip() for part in result.stdout.splitlines()[0].split(",")[:4]]
        return {
            "gpu_util_percent": to_float(util),
            "gpu_memory_used_mb": to_float(mem_used),
            "gpu_temp_c": to_float(temp),
            "gpu_power_w": to_float(power),
        }
    except Exception:
        return None


def read_online_status() -> dict[str, Any] | None:
    try:
        with urlopen("http://127.0.0.1:8000/status", timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def collect_system_snapshot(device: str) -> dict[str, Any]:
    props = torch.cuda.get_device_properties(0)
    return {
        "python": sys.executable,
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "device_requested": device,
        "device_name": torch.cuda.get_device_name(0),
        "gpu_total_memory_mb": round(props.total_memory / (1024 * 1024), 2),
        "nvidia_smi": query_nvidia_smi_version(),
    }


def query_nvidia_smi_version() -> dict[str, Any] | None:
    command = ["nvidia-smi", "--query-gpu=driver_version,name", "--format=csv,noheader"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=3)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        driver_version, gpu_name = [part.strip() for part in result.stdout.splitlines()[0].split(",")[:2]]
        return {"driver_version": driver_version, "gpu_name": gpu_name}
    except Exception:
        return None


def build_summary(
    runs: list[dict[str, Any]],
    online_status: dict[str, Any] | None,
    service_config: dict[str, Any],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    categories = {
        "detect_only": "best_detect_only",
        "pose_only": "best_pose_only",
        "detect_pose_sequential": "best_detect_pose_sequential",
        "detect_pose_with_inference_lock": "best_detect_pose_with_inference_lock",
        "target_only_pose_crop": "best_target_only_pose_crop",
        "full_frame_pose_low_frequency": "best_full_frame_pose_low_frequency",
    }
    for category, key in categories.items():
        items = [run for run in runs if run["category"] == category]
        if items:
            best = max(items, key=lambda item: float(item.get("fps") or 0.0))
            summary[key] = {
                "scenario": best["scenario"],
                "fps": best["fps"],
                "avg_latency_ms": best.get("avg_latency_ms"),
                "p95_latency_ms": best.get("p95_latency_ms"),
                "gpu_util_avg_percent": (best.get("gpu") or {}).get("gpu_util_avg_percent"),
                "gpu_util_max_percent": (best.get("gpu") or {}).get("gpu_util_max_percent"),
            }

    summary["threshold_checks"] = {
        "detect_over_15fps": best_fps(runs, "detect_only") > 15.0,
        "pose_over_5fps": best_fps(runs, "pose_only") > 5.0,
        "detect_pose_sequential_over_5fps": best_fps(runs, "detect_pose_sequential") > 5.0,
        "gpu_util_over_50_percent_seen": best_gpu_util(runs) > 50.0,
    }

    summary["half_impact"] = {
        "detect_only": paired_half_speedup(runs, "detect_only"),
        "pose_only": paired_half_speedup(runs, "pose_only"),
        "detect_pose_sequential": paired_half_speedup(runs, "detect_pose_sequential"),
        "target_only_pose_crop": paired_half_speedup(runs, "target_only_pose_crop"),
    }
    summary["imgsz_impact"] = {
        "detect_only": imgsz_speed_table(runs, "detect_only"),
        "pose_only": imgsz_speed_table(runs, "pose_only"),
        "detect_pose_sequential": imgsz_speed_table(runs, "detect_pose_sequential"),
    }

    online_detection_fps = online_status_value(online_status, ("detection", 0, "detection_fps"))
    online_pose_fps = online_status_value(online_status, ("pose", "pose_fps"))
    detection_worker_cap = service_config.get("detection_worker_cap_fps")
    best_detect = best_fps(runs, "detect_only")
    summary["bottleneck_assessment"] = {
        "online_detection_fps": online_detection_fps,
        "online_pose_fps": online_pose_fps,
        "configured_detection_worker_cap_fps": detection_worker_cap,
        "offline_best_detect_fps": best_detect,
        "assessment": build_bottleneck_text(best_detect, online_detection_fps, detection_worker_cap),
    }
    return summary


def build_bottleneck_text(best_detect: float, online_detection_fps: float | None, detection_worker_cap: float | None) -> str:
    if online_detection_fps is None:
        return "No live /status snapshot was available during the benchmark."
    if detection_worker_cap is not None and best_detect > detection_worker_cap * 2:
        return (
            "Offline detect throughput is far above the current worker cap, so the live 3-5 FPS range is primarily "
            "runtime scheduling / capture cadence bound, not raw YOLO model bound."
        )
    if best_detect > online_detection_fps * 2:
        return "Offline detect throughput is much higher than live throughput, so runtime scheduling overhead is the main limiter."
    return "Offline detect throughput is close to live throughput, so model inference is a primary limiter."


def paired_half_speedup(runs: list[dict[str, Any]], category: str) -> dict[str, Any]:
    fp32: dict[str, float] = {}
    fp16: dict[str, float] = {}
    for run in runs:
        if run["category"] != category:
            continue
        key = half_pair_key(run)
        if run.get("half"):
            fp16[key] = float(run.get("fps") or 0.0)
        else:
            fp32[key] = float(run.get("fps") or 0.0)
    deltas = []
    per_key = {}
    for key, base in fp32.items():
        faster = fp16.get(key)
        if faster is None or base <= 0:
            continue
        uplift = ((faster - base) / base) * 100.0
        per_key[key] = round(uplift, 2)
        deltas.append(uplift)
    return {
        "pairs": per_key,
        "avg_percent": round(mean(deltas), 2) if deltas else None,
        "max_percent": round(max(deltas), 2) if deltas else None,
    }


def imgsz_speed_table(runs: list[dict[str, Any]], category: str) -> dict[str, Any]:
    values: dict[str, dict[str, float]] = {}
    for run in runs:
        if run["category"] != category:
            continue
        half_label = "fp16" if run.get("half") else "fp32"
        imgsz = run.get("imgsz") or run.get("detect_imgsz")
        values.setdefault(half_label, {})[str(imgsz)] = float(run.get("fps") or 0.0)
    return values


def half_pair_key(run: dict[str, Any]) -> str:
    detect_imgsz = run.get("detect_imgsz")
    pose_imgsz = run.get("pose_imgsz")
    if detect_imgsz is not None or pose_imgsz is not None:
        return f"d{detect_imgsz}_p{pose_imgsz}"
    imgsz = run.get("imgsz")
    return f"i{imgsz}"


def best_fps(runs: list[dict[str, Any]], category: str) -> float:
    items = [float(run.get("fps") or 0.0) for run in runs if run["category"] == category]
    return max(items) if items else 0.0


def best_gpu_util(runs: list[dict[str, Any]]) -> float:
    values = []
    for run in runs:
        gpu = run.get("gpu") or {}
        value = gpu.get("gpu_util_max_percent")
        if isinstance(value, (int, float)):
            values.append(float(value))
    return max(values) if values else 0.0


def online_status_value(status: dict[str, Any] | None, path: tuple[Any, ...]) -> float | None:
    current: Any = status
    for item in path:
        if current is None:
            return None
        if isinstance(item, int):
            if not isinstance(current, list) or len(current) <= item:
                return None
            current = current[item]
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(item)
    return float(current) if isinstance(current, (int, float)) else None


def assert_cuda_ready(device: str) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("torch.cuda.is_available() is false; this benchmark requires CUDA.")
    if not str(device).lower().startswith("cuda"):
        raise RuntimeError(f"device must point to CUDA for this benchmark, got: {device}")


def sync_cuda() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def predictor_device(model) -> str | None:
    predictor = getattr(model, "predictor", None)
    device = getattr(predictor, "device", None)
    return str(device) if device is not None else None


def release_model(model) -> None:
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def shape_of(frame: np.ndarray) -> dict[str, int]:
    height, width = frame.shape[:2]
    return {"width": int(width), "height": int(height)}


def bbox_area(bbox: list[float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def sleep_until(target: float) -> None:
    delay = target - time.perf_counter()
    if delay > 0:
        time.sleep(delay)


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def utc_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
