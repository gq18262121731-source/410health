# 给 AI 员工的快速优化提示词

把下面整段复制给负责部署的 AI 员工。使用前请把本机路径、摄像头密码、Python 环境路径按实际情况修改。不要把真实密码提交到 Git。

```text
你是一个资深全栈工程师。当前项目是 410health 老人健康检测平台，我已经从 GitHub 拉取了初始项目，现在需要你把摄像头实时监控、跌倒检测模型、本地告警融合、ROI 检测区域和系统测试文档快速部署到和团队核心优化分支一致的状态。

请严格按以下目标执行：

1. 先确认当前仓库状态
   - 执行 git status，确认是否有本地未提交改动。
   - 不要覆盖我本地已有的私有配置文件。
   - 不要提交 .env、logs、data/fall_events 或任何真实密码。

2. 拉取团队核心优化分支
   - 仓库地址：https://github.com/gq18262121731-source/410health.git
   - 分支名：feature/camera-fall-roi-core-optimization
   - 如果当前目录已经是仓库，执行：
     git fetch origin
     git checkout feature/camera-fall-roi-core-optimization
     git pull
   - 如果当前目录不是仓库，执行：
     git clone --branch feature/camera-fall-roi-core-optimization --single-branch https://github.com/gq18262121731-source/410health.git

3. 配置本地 .env
   - 复制 .env.example 为 .env。
   - 按本机情况填写摄像头和模型路径：
     CAMERA_IP=192.168.8.253
     CAMERA_USER=admin
     CAMERA_PASSWORD=这里填写实际摄像头密码
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
     FALL_DETECTION_PYTHON=这里填写本机 AI 环境 python.exe
     FALL_DETECTION_SPEED_PROFILE=accuracy
     FALL_DETECTION_ROI_ENABLED=true
     FALL_DETECTION_ROI_RECT=0.18,0.32,0.82,0.94
     FALL_DETECTION_ROI_MIN_OVERLAP=0.50
     FALL_DETECTION_FRAME_WIDTH=2304
     FALL_DETECTION_FRAME_HEIGHT=1296
     FALL_DETECTION_MIN_ALERT_SCORE=0.0

4. 确认跌倒检测模型
   - 模型根目录应该包含 scripts/realtime_fall_monitor.py。
   - 确认模型权重、configs 和 scripts 都存在。
   - 不要为了提速改成 fast 或 half；当前要求是 accuracy，不能降低检测精度。

5. 启动项目
   - 后端：
     python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   - 前端：
     cd frontend/vue-dashboard
     npm install
     npm run dev

6. 检查摄像头与模型状态
   - 打开：
     http://127.0.0.1:8000/api/v1/camera/stream-status
     http://127.0.0.1:8000/api/v1/camera/fall-detection/status
   - 期望：
     stream running 为 true
     source_fps 有数值
     fall detection enabled 为 true
     process_running 为 true
     accuracy_preserving 为 true
     roi.enabled 为 true

7. 前端验证
   - 打开前端页面。
   - 确认监控视频可以实时显示。
   - 触发模拟跌倒接口或使用安全模拟跌倒样本。
   - 确认系统弹出跌倒警报。
   - 点击“确认处理并解除警报”，确认弹窗消失且不会立即重复弹出旧告警。

8. ROI 与现场校准
   - 阅读 docs/fall-detection-roi-calibration-guide-2026-04-30.md。
   - 先使用默认 ROI：0.18,0.32,0.82,0.94。
   - 用 10 到 20 分钟空场景、正常走路、坐下、弯腰、窗帘强光扰动、安全模拟跌倒进行验证。
   - 如果误报集中在边缘，微调 ROI。
   - 不要把 ROI 缩得过小，床边、沙发边、老人主要活动区必须保留。

9. 跑基础检查
   - 后端语法：
     python -m py_compile backend/config.py backend/dependencies.py backend/services/fall_detection_service.py
   - 前端构建：
     cd frontend/vue-dashboard
     npm run build

10. 最后输出结果
   - 汇报修改了哪些本地配置。
   - 汇报摄像头流状态、模型状态、ROI 状态。
   - 汇报功能测试结果：视频、模型、告警、解除告警、ROI。
   - 明确说明没有提交真实密码，没有降低模型精度。
```

## 重要安全提醒

不要让 AI 员工执行以下行为：

```text
把真实 CAMERA_PASSWORD 写进 Git
把 GitHub 密码或 PAT 写进文件
把 .env 加入 git add
把 FALL_DETECTION_SPEED_PROFILE 改成 fast 来掩盖性能问题
删除用户已有本地改动
```
