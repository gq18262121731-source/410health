# Phase 5.17 AI Throughput Benchmark

## Scope

Phase 5.17 benchmarks local AI inference throughput on the RTX 4060 Ti class machine in offline / side-path mode.

This phase does not modify:

- Detection worker
- Pose worker
- Temporal
- Result publisher
- WebRTC
- Dual-stream runtime
- TensorRT / ONNX deployment path
- Cloud deployment

## Goal

Validate whether the current online `3.5 FPS` range is caused by raw model inference or by runtime scheduling / worker cadence.

## Benchmark Entry

Script:

```text
scripts/benchmark_ai_throughput.py
```

Artifacts:

```text
logs/runtime_debug/phase5_17_ai_throughput_benchmark.json
docs/phase5_17_ai_throughput_benchmark.md
```

## Test Environment

Measured on `2026-05-26`.

```text
Python: C:\Users\13010\anaconda3\envs\torchgpu\python.exe
Torch: 2.6.0+cu124
CUDA: 12.4
GPU: NVIDIA GeForce RTX 4060 Laptop GPU
Driver: 591.86
Device: cuda:0
```

Input used for the formal benchmark run:

```text
Source: local video
Path: tests/fixtures/person_bus_loop.mp4
Resolution: 810x1080
Source FPS: 12
Measured frames per case: 80
Warmup frames per case: 12
```

The script also supports:

- local video
- RTSP URL
- synthetic warmup/random frame input

## Live Runtime Snapshot During Benchmark

At benchmark time, `/status` showed:

```text
online detection_fps: 3.48
online detection latency: 85.56 ms
online pose_fps: 0.03
online pose latency: 110.0 ms
online pose skipped_due_to_busy: 88
detection_interval_ms: 200
configured detection worker cap: 5.0 FPS
pose_worker_fps: 2.0
pose_skip_when_inference_busy: true
```

This is the key comparison baseline for deciding whether the bottleneck is inference or runtime scheduling.

## Results

### A. Detect only

Best result:

```text
yolov8n.pt
imgsz=320
half=false
FPS=134.18
avg latency=7.44 ms
P95 latency=10.69 ms
GPU util avg/max=44% / 48%
```

Reference points:

```text
640 fp32: 120.49 FPS
512 fp32: 125.81 FPS
416 fp32: 125.64 FPS
320 fp32: 134.18 FPS
```

Conclusion:

- Detect-only throughput is far above `15 FPS`.
- Detect itself is not the limiting factor in the live service.

### B. Pose only

Best result:

```text
yolov8n-pose.pt
imgsz=320
half=false
FPS=114.02
avg latency=8.76 ms
P95 latency=11.30 ms
GPU util avg/max=34.33% / 43%
```

Reference points:

```text
640 fp32: 110.71 FPS
512 fp32: 108.94 FPS
416 fp32: 106.93 FPS
320 fp32: 114.02 FPS
```

Conclusion:

- Pose-only throughput is far above `5 FPS`.
- Raw YOLO-Pose is also not the limiting factor in the live service.

### C. Detect + pose sequential

Best result:

```text
detect: yolov8n.pt
pose: yolov8n-pose.pt
imgsz=416/416
half=false
FPS=57.73
avg latency=17.30 ms
P95 latency=23.79 ms
GPU util avg/max=33.67% / 37%
```

Reference points:

```text
640/640 fp32: 53.67 FPS
512/512 fp32: 52.28 FPS
416/416 fp32: 57.73 FPS
320/320 fp32: 56.42 FPS
```

Conclusion:

- Sequential detect+pose throughput is far above `5 FPS`.
- Even without pipeline parallelism, the machine has large inference headroom.

### D. Detect + pose with inference lock

This case simulates the current service behavior pattern:

- detect loop capped by `DETECTION_INTERVAL_MS=200`
- pose worker at `POSE_WORKER_FPS=2`
- shared `ultralytics_inference_lock`
- pose non-blocking acquire behavior

Best result:

```text
scenario: detect_pose_lock_service_baseline_fp32
detect imgsz=640
pose imgsz=320
FPS=5.00
detect avg latency=9.58 ms
detect P95 latency=14.46 ms
pose_fps=1.25
pose_skipped_due_to_busy=12
GPU util avg/max=11.78% / 26%
```

Other lock-sim results:

```text
baseline fp16: detect FPS=4.99, pose_fps=1.18, skipped=13
tuned fp16 (416/320): detect FPS=4.99, pose_fps=1.06, skipped=15
```

Conclusion:

- This mode reproduces the live-service shape very closely.
- GPU utilization stays low because the runtime intentionally throttles work.
- The live `3.5 FPS` class behavior is mainly worker cadence / lock policy / service scheduling bound.

### E. Target-only pose

#### Target crop pose every frame

Best result:

```text
detect imgsz=416
pose imgsz=320
half=false
FPS=60.42
avg latency=15.72 ms
P95 latency=20.14 ms
GPU util avg/max=36.5% / 48%
```

#### Full-frame pose at low frequency

Best result:

```text
detect imgsz=640
pose imgsz=320
pose every 5 frames
half=false
FPS=97.97
avg latency=10.19 ms
P95 latency=16.48 ms
GPU util avg/max=44% / 46%
```

Conclusion:

- Lowering pose frequency is highly effective when we care about whole-pipeline throughput.
- Crop-based target pose also works well, but in this benchmark it did not outperform simple sequential detect+pose by a huge margin because the test clip is easy and single-target-heavy.

## FP16 Evaluation

Observed effect in this PyTorch + Ultralytics path:

```text
detect_only average uplift: -4.51%
pose_only average uplift: -4.31%
detect+pose sequential average uplift: -4.98%
target-only crop pose average uplift: -2.43%
```

Interpretation:

- `half=true` did not provide a stable win in this environment.
- Some single cases were slightly faster, but the overall average was slightly slower.
- FP16 is not currently worth promoting as the default competition setting in the existing Python/Ultralytics path.

## ImgSz Evaluation

Key trend:

- Detect-only: `320` was fastest.
- Pose-only: `320` was fastest.
- Detect+pose sequential: `416` was the best balance in this benchmark.

Practical interpretation:

- `416` is a sensible default if we want lower latency without aggressively shrinking the image.
- `320` is valid if runtime pressure becomes more important than recall margin.
- Since live throughput is not inference-bound today, imgsz tuning is useful but not the main unlock.

## Bottleneck Decision

The central comparison is:

```text
offline best detect_only: 134.18 FPS
offline best pose_only: 114.02 FPS
offline best detect+pose sequential: 57.73 FPS
live detection_fps during benchmark: 3.48
configured detection worker cap: 5.0 FPS
live pose_fps during benchmark: 0.03
live pose skipped_due_to_busy: 88
```

Decision:

```text
Current online 3.5 FPS is not a raw YOLO model bottleneck.
Current online behavior is primarily runtime scheduling / cadence / lock-policy limited.
```

More specifically:

- Detection is artificially capped by `DETECTION_INTERVAL_MS=200`, which already limits the worker to about `5 FPS`.
- Pose is further reduced by `POSE_WORKER_FPS=2` plus shared lock contention plus non-blocking skip behavior.
- GPU utilization remains low in the lock-sim case because the system is not feeding the GPU aggressively.

## Answers To The Target Questions

### 1. Can offline detect exceed 15 FPS?

Yes.

```text
Best detect-only = 134.18 FPS
```

### 2. Can offline pose exceed 5 FPS?

Yes.

```text
Best pose-only = 114.02 FPS
```

### 3. Can sequential detect+pose exceed 5 FPS?

Yes.

```text
Best sequential detect+pose = 57.73 FPS
```

### 4. Is the current online 3.5 FPS due to inference or runtime?

Runtime.

```text
Offline detect is 38x+ higher than live detect_fps.
Configured detection worker cap is only 5 FPS.
```

### 5. Does `half=True` help significantly?

No.

In this environment it is not a meaningful win, and average results were slightly worse.

### 6. Do `imgsz=416/320` help significantly?

They help somewhat, but not enough to explain the live bottleneck.

- `320` helps the single-model microbenchmarks.
- `416` is the best sequential combined setting in this run.
- The live service still remains runtime-limited after such tuning.

### 7. Can GPU util exceed 50%?

Yes, but only briefly in the offline benchmark path.

Examples:

```text
detect 640 fp16 gpu max: 51%
pose 640 fp32 gpu max: 56%
```

In the lock-sim / live-like configuration, GPU util stayed much lower:

```text
lock-sim gpu avg: 11.78% - 13.65%
lock-sim gpu max: 26% - 34%
```

## Current Local Maximum AI Throughput

Based on this benchmark run:

```text
Max detect-only: 134.18 FPS
Max pose-only: 114.02 FPS
Max detect+pose sequential: 57.73 FPS
Max target-crop detect+pose: 60.42 FPS
Max low-frequency full-frame pose pipeline: 97.97 FPS
Live-like lock-sim detect throughput: 5.00 FPS
```

If the question is "what is the current real service-like maximum under current lock/cadence policy?", the answer is:

```text
about 5 FPS detect loop
about 1.1 - 1.25 FPS pose loop
```

## Recommended Competition Configuration

Recommended near-term competition/runtime direction:

```text
Keep local deployment on the 4060 Ti
Keep cuda:0
Keep current dual-stream architecture
Do not move to cloud
Do not move to TensorRT yet
```

Recommended AI settings for the current service family:

```text
YOLO detect imgsz: 416 or 512
YOLO pose imgsz: 320
half: false
pose should not run on every possible tick
pose should stay target-only or low-frequency
```

Recommended operational strategy:

```text
Detection can stay frequent
Pose should be reduced in frequency
Pose should stay target-only when possible
```

## Whether FP16 Is Worth It

Current answer:

```text
Not worth it as the default.
```

Reason:

- No consistent throughput win
- Sometimes slower
- Does not solve the real online bottleneck

## Whether ONNX / TensorRT Is Worth It

Current answer:

```text
Not yet.
```

Reason:

- Offline PyTorch throughput is already far above the live requirement.
- The current bottleneck is runtime cadence and lock behavior, not raw model speed.
- ONNX/TensorRT would add environment complexity before addressing the real limiting factor.

Recommended order remains:

```text
runtime scheduling / pose frequency / target-only pose
-> imgsz tuning
-> only then consider ONNX or TensorRT if a later phase still needs more headroom
```

## Whether Pose Frequency Should Be Lowered

Yes.

This benchmark strongly supports lowering pose frequency in the live service path.

Reason:

- Raw pose inference is already fast enough.
- The live bottleneck comes from how often pose is attempted and how it contends for the shared inference lock.
- Low-frequency full-frame pose and target-only pose both preserve strong throughput while reducing contention.

Recommended direction:

```text
pose should remain reduced-frequency
pose should prefer target-only
pose imgsz should stay near 320
```

## Final Decision

Phase 5.17 shows that the 4060 Ti has more than enough local AI inference headroom for the demo.

The immediate next optimization priority is not cloud and not TensorRT. It is:

```text
runtime scheduling
pose frequency reduction
target-only pose policy
optional imgsz reduction
```

The machine is already strong enough. The current online limit is mostly how the pipeline feeds the GPU, not whether the GPU can run the models.
