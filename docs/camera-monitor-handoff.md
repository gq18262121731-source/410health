# 摄像头监控功能交接文档

本文档给已经有本项目本地仓库的同事使用，目标是把摄像头监控分支更新到自己的项目里，并完成本地配置、启动和验证。

## 1. 分支和代码地址

远程仓库：

```bash
https://github.com/gq18262121731-source/410health.git
```

摄像头功能分支：

```bash
codex/camera-monitor
```

分支页面：

```text
https://github.com/gq18262121731-source/410health/tree/codex/camera-monitor
```

如果是全新拉取项目：

```bash
git clone -b codex/camera-monitor https://github.com/gq18262121731-source/410health.git
cd 410health
```

如果本地已经有项目：

```bash
cd 你的项目目录
git status
```

如果 `git status` 显示有本地改动，请先提交或暂存，避免更新时冲突：

```bash
git add .
git commit -m "Save local work before camera update"
```

或者只是临时保存：

```bash
git stash push -m "before camera update"
```

然后拉取摄像头分支：

```bash
git fetch origin
git checkout codex/camera-monitor
git pull origin codex/camera-monitor
```

如果你要把摄像头功能合并进自己的开发分支：

```bash
git checkout 你的开发分支
git merge origin/codex/camera-monitor
```

如有冲突，优先保留摄像头相关文件里的新增接口和组件，再按实际业务页面调整。

## 2. 本次功能包含什么

后端新增能力：

- 摄像头 RTSP 配置读取，不把密码写死在代码里。
- `/api/v1/camera/status`：检测摄像头是否在线。
- `/api/v1/camera/snapshot`：获取当前截图。
- `/api/v1/camera/stream-status`：查看视频流诊断信息，例如源帧率、广播帧率、当前连接数。
- `/api/v1/camera/ptz`：控制 ONVIF 云台转动、停止、拉近、拉远。
- `/ws/camera`：后端只连接摄像头一次，再通过 WebSocket 转发给前端。

前端新增能力：

- 家属端页面加入“家中实时看护”监控卡片。
- 使用 WebSocket 接收后端视频帧。
- 使用 canvas 绘制最新帧，避免图片帧堆积造成延迟。
- 支持模拟摇杆，按住连续转动，松开停止。
- 显示前端实收 fps、后端源流 fps、局域网延迟等诊断信息。

辅助脚本：

- `scripts/camera_probe.py`：测试 RTSP 路径并保存截图。
- `scripts/camera_fps_probe.py`：直连摄像头 RTSP 测试源帧率。
- `scripts/camera_ws_fps_probe.py`：测试后端 WebSocket 实际输出帧率。

## 3. 本地环境准备

Python 环境以本机实际 conda 环境为准。当前开发机使用的是：

```text
C:\Users\13010\anaconda3\envs\helth\python.exe
```

如果你的环境名是 `health` 或其它名字，把下面命令里的路径替换成自己的 Python。

安装后端依赖：

```bash
pip install -r requirements.txt
```

前端依赖：

```bash
cd frontend/vue-dashboard
npm install
```

## 4. 摄像头配置

不要把真实摄像头密码提交到 GitHub。请在项目根目录创建或更新 `.env`：

```env
CAMERA_IP=192.168.8.253
CAMERA_USER=admin
CAMERA_PASSWORD=实际摄像头密码
CAMERA_RTSP_PATH=/tcp/av0_0
CAMERA_RTSP_PORT=10554
CAMERA_ONVIF_PORT=10080
CAMERA_STREAM_RTSP_PATH=/tcp/av0_1
CAMERA_STREAM_FPS=24
CAMERA_PTZ_MOVE_SECONDS=0.35
CAMERA_PTZ_SPEED=0.45
```

说明：

- `CAMERA_IP` 是摄像头在局域网里的 IP。
- `CAMERA_PASSWORD` 需要由项目负责人私下交接，不进入代码仓库。
- `CAMERA_STREAM_RTSP_PATH=/tcp/av0_1` 当前用于视频流，延迟较低。
- `CAMERA_RTSP_PATH=/tcp/av0_0` 当前用于截图和状态展示。
- `CAMERA_ONVIF_PORT=10080` 用于云台控制。

## 5. 启动项目

启动后端：

```bash
cd 项目根目录
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

如果使用指定 Python：

```bash
C:\Users\13010\anaconda3\envs\helth\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

启动前端：

```bash
cd frontend/vue-dashboard
npm run dev -- --host 127.0.0.1
```

浏览器访问：

```text
http://127.0.0.1:5173/#/family
```

如果跳到登录页，可以使用项目演示家属账号登录，例如：

```text
账号：family01
密码：123456
```

## 6. 验证摄像头是否正常

先确认电脑和摄像头在同一个局域网：

```powershell
ping 192.168.8.253
```

测试 RTSP 截图：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_probe.py
```

测试摄像头源帧率：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_fps_probe.py
```

测试后端 WebSocket 输出帧率：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_ws_fps_probe.py
```

查看后端流状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera/stream-status | ConvertTo-Json -Depth 4
```

正常情况下可以看到类似：

```json
{
  "clients": 1,
  "running": true,
  "last_error": null,
  "target_fps": 24.0,
  "source_fps": 20.0,
  "active_url": "rtsp://admin:***@192.168.8.253:10554/tcp/av0_1"
}
```

注意：

- `active_url` 里的密码会被后端自动打码。
- `source_fps` 代表摄像头源流帧率。
- `broadcast_fps` 是广播总帧数，多客户端连接时可能会高于源流 fps。
- 前端卡片里更应该看“实收 fps”和“后端源流 fps”。

## 7. 常见问题

### 页面一直显示连接中

优先检查：

```powershell
ping 192.168.8.253
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera/stream-status | ConvertTo-Json -Depth 4
```

如果 `last_error` 是 `CAMERA_STREAM_READ_TIMEOUT`，通常是电脑当前没有连到摄像头所在局域网，或者摄像头 RTSP 服务未响应。

### 后端在线，但前端没有画面

检查浏览器是否在家属端页面：

```text
http://127.0.0.1:5173/#/family
```

再检查 WebSocket：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_ws_fps_probe.py
```

如果脚本能测到帧率，但页面没有画面，优先看浏览器控制台是否有前端报错。

### 云台不动或不灵敏

检查 `.env`：

```env
CAMERA_ONVIF_PORT=10080
CAMERA_PTZ_SPEED=0.45
```

如果能动但太慢，可以适当调高：

```env
CAMERA_PTZ_SPEED=0.6
```

调整后需要重启后端。

### 视频延迟大

建议先看三个指标：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_fps_probe.py
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_ws_fps_probe.py
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera/stream-status | ConvertTo-Json -Depth 4
```

判断方式：

- RTSP 源帧率低：摄像头或网络问题。
- RTSP 源帧率正常，但 WebSocket 低：后端转码/转发问题。
- WebSocket 正常，但页面低：前端渲染或浏览器压力问题。

## 8. 重要安全说明

不要提交以下内容：

- `.env`
- 摄像头真实密码
- 摄像头私有 SDK 大包或解压目录
- 日志文件
- 临时截图目录

真实密码请通过线下、企业 IM 私密消息或密码管理器交接。即使后续从 GitHub 删除，密码仍可能留在 git 历史里。

## 9. 本次主要文件

后端：

```text
backend/api/camera_api.py
backend/services/camera_service.py
backend/services/camera_stream_hub.py
backend/config.py
backend/dependencies.py
backend/main.py
```

前端：

```text
frontend/vue-dashboard/src/components/CameraMonitorCard.vue
frontend/vue-dashboard/src/views/FamilyPage.vue
frontend/vue-dashboard/src/api/client.ts
```

脚本：

```text
scripts/camera_probe.py
scripts/camera_fps_probe.py
scripts/camera_ws_fps_probe.py
```

配置示例：

```text
.env.example
```
