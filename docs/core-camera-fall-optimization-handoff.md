# 410health 摄像头与跌倒检测核心优化交付说明

日期：2026-04-30

## 分支用途

本分支用于把已完成的摄像头实时监控、跌倒检测模型接入、实时告警弹窗、ROI 检测区域、现场样本校准与测试文档合并成一套可交付的核心优化包。团队成员可以在已有初始项目的基础上拉取本分支，快速同步到当前优化程度。

## 核心能力

1. 摄像头实时画面接入
   - 后端统一管理 RTSP 拉流。
   - 前端使用低延迟预览流展示实时画面。
   - 模型使用主码流保持检测画质。

2. 跌倒检测模型本地部署
   - 后端启动并守护本地跌倒检测模型进程。
   - 模型事件通过 JSONL 实时进入主系统。
   - 保持 `accuracy` 配置，不降低模型检测精度。

3. 平台告警融合
   - 模型确认跌倒后生成系统告警。
   - 前端弹出跌倒警报大弹窗。
   - 告警面板展示截图、风险等级、伤情建议与处理状态。
   - 支持一键处理并解除当前活跃跌倒告警。

4. ROI 检测区域
   - ROI 只作为“系统告警准入过滤”，不修改模型推理结果。
   - 模型仍完整检测整幅画面并保留原始事件。
   - 系统只过滤明显位于窗帘、强光、画面边缘等非老人活动区的告警。

5. 测试与校准文档
   - 系统功能、性能、跌倒模拟、告警解除、现场 ROI 校准均有文档。

## 本分支核心文件

后端：

```text
backend/api/alarm_api.py
backend/api/camera_api.py
backend/config.py
backend/dependencies.py
backend/main.py
backend/models/alarm_model.py
backend/services/alarm_service.py
backend/services/camera_service.py
backend/services/camera_stream_hub.py
backend/services/fall_detection_service.py
backend/services/websocket_manager.py
```

前端：

```text
frontend/vue-dashboard/src/api/client.ts
frontend/vue-dashboard/src/components/AlarmPanel.vue
frontend/vue-dashboard/src/components/CameraMonitorCard.vue
frontend/vue-dashboard/src/components/layout/AppShell.vue
frontend/vue-dashboard/src/components/layout/FallAlertOverlay.vue
frontend/vue-dashboard/src/views/MemberDevicePage.vue
```

配置与文档：

```text
.env.example
docs/fall-detection-roi-calibration-guide-2026-04-30.md
docs/system-acceptance-test-plan-2026-04-30.md
docs/system-acceptance-test-report-2026-04-30.md
docs/core-camera-fall-optimization-handoff.md
docs/ai-worker-camera-fall-optimization-prompt.md
```

## 本地环境配置

复制 `.env.example` 为 `.env`，然后根据本机环境修改：

```env
CAMERA_IP=192.168.8.253
CAMERA_USER=admin
CAMERA_PASSWORD=replace-with-your-camera-password
CAMERA_RTSP_PATH=/tcp/av0_0
CAMERA_RTSP_PORT=10554
CAMERA_ONVIF_PORT=10080

CAMERA_STREAM_PROFILE=smooth
CAMERA_STREAM_QUALITY_PATH=/tcp/av0_0
CAMERA_STREAM_SMOOTH_PATH=/tcp/av0_1
CAMERA_STREAM_FPS=15
CAMERA_STREAM_WIDTH=960
CAMERA_STREAM_JPEG_QUALITY=5

FALL_DETECTION_ENABLED=true
FALL_DETECTION_MODEL_ROOT=D:/Program/model/fall_detection
FALL_DETECTION_PYTHON=C:/Users/YOUR_NAME/.conda/envs/AI/python.exe
FALL_DETECTION_SPEED_PROFILE=accuracy
FALL_DETECTION_ROI_ENABLED=true
FALL_DETECTION_ROI_RECT=0.18,0.32,0.82,0.94
```

注意：真实摄像头密码、GitHub token、模型 API key 只放在本地 `.env`，不要提交到 Git。

## 启动与验证

后端：

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

前端：

```powershell
cd frontend/vue-dashboard
npm install
npm run dev
```

检查接口：

```text
http://127.0.0.1:8000/api/v1/camera/stream-status
http://127.0.0.1:8000/api/v1/camera/fall-detection/status
```

预期：

```text
camera stream running = true
fall detection enabled = true
fall detection process_running = true
accuracy_preserving = true
roi.enabled = true
```

## 推荐验收项

1. 前端能看到实时摄像头画面。
2. 跌倒检测状态接口显示模型进程运行中。
3. 模拟跌倒事件后前端弹出跌倒警报。
4. 点击“确认处理并解除警报”后弹窗消失。
5. 画面无人或边缘强光扰动时不频繁弹出误报。
6. ROI 内安全模拟跌倒时仍能触发告警。

## 不包含内容

本分支不提交：

```text
.env
logs/
data/fall_events/
真实摄像头密码
GitHub 登录密码或 PAT
本机临时进程文件
```
