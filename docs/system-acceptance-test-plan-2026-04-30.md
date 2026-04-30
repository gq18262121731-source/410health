# 智慧养老健康监测平台全方位系统测试计划

更新日期：2026-04-30
适用范围：实时监控视频、跌倒检测模型、健康手环数据、告警闭环、社区端前端体验、本地部署稳定性。

## 1. 测试目标

本轮测试不是只验证“页面能打开”，而是验证系统是否符合老人健康守护平台的真实业务逻辑：

- 摄像头视频能稳定接入系统，前端能看到实时画面。
- 跌倒检测模型作为后台服务持续运行，并且不降低精度。
- 模型事件能转为系统告警、截图、风险等级和处理建议。
- 告警弹窗、活动告警列表、声音提醒和确认处理能形成闭环。
- 点击“确认处理并解除警报”后，弹窗应消失，同一批告警不应马上反复弹出。
- 摄像头断线、模型异常、浏览器断连、重复告警等情况有合理表现。
- 功能、性能、体验和安全隐私都能被验收。

## 2. 当前关键架构

```text
摄像头 RTSP
  ├─ CameraFrameHub
  │   ├─ WebSocket 视频帧
  │   └─ MJPEG 兜底流
  │
  └─ FallDetectionService
      └─ realtime_fall_monitor.py
          └─ camera_events.jsonl / snapshots
              └─ AlarmService
                  ├─ 活动告警
                  ├─ 告警队列
                  ├─ WebSocket 广播
                  └─ 前端全屏跌倒告警
```

当前设计原则：

- 前端预览可使用辅码流以保证流畅。
- 跌倒模型必须保持 `accuracy` 精度优先模式，不主动跳帧、不主动缩放、不默认半精度。
- 告警解除应批量处理同一批跌倒告警，并设置短冷却，避免重复弹窗。

## 3. 验收环境

后端：

```text
http://127.0.0.1:8000
```

前端：

```text
http://127.0.0.1:5173
```

关键接口：

```text
GET  /api/v1/camera/status
GET  /api/v1/camera/stream-status
GET  /api/v1/camera/fall-detection/status
GET  /api/v1/alarms?active_only=true
GET  /api/v1/alarms/queue
POST /api/v1/alarms/fall/acknowledge-active
POST /api/v1/camera/fall-detection/simulate
```

关键本地目录：

```text
data/fall_events/camera_events.jsonl
data/fall_events/snapshots/
logs/backend.err.log
logs/backend.out.log
logs/frontend.err.log
logs/frontend.out.log
```

## 4. 通过标准总览

必须满足：

- 后端 8000 端口在线。
- 前端 5173 端口在线。
- 跌倒检测服务 `enabled=true`、`running=true`、`process_running=true`。
- 跌倒检测 `speed_profile=accuracy`、`accuracy_preserving=true`。
- 同一时间只应有一个 `realtime_fall_monitor.py` 进程。
- 同一时间只应有一个 `backend.main:app` 后端进程。
- 活动跌倒告警可通过批量确认接口解除。
- 批量确认后 5 秒内不应再次出现同一批跌倒弹窗。
- WebSocket 广播不能因为断开的浏览器连接导致确认接口卡死。
- 摄像头不可达时，前端应显示异常状态，而不是假装正常。

## 5. 功能测试

### F-001 后端服务启动

步骤：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera/fall-detection/status
```

预期：

- 8000 端口存在监听进程。
- 接口返回 200。
- 无 Python 启动异常。

### F-002 前端服务启动

步骤：

```powershell
Get-NetTCPConnection -LocalPort 5173 -State Listen
```

预期：

- 5173 端口存在监听进程。
- 浏览器打开 `http://127.0.0.1:5173` 能进入登录页或工作台。

### F-003 摄像头在线状态

步骤：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera/status
```

预期：

- `configured=true`
- 摄像头可达时 `online=true`、`error=null`
- 摄像头不可达时应明确返回错误，不应误报在线。

### F-004 实时视频流

步骤：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera/stream-status
```

预期：

- 正常时 `running=true`
- `latest_frame_at` 持续更新
- `source_fps` 接近目标帧率
- `last_error=null`

异常判定：

- `CAMERA_STREAM_READ_TIMEOUT` 表示 RTSP 读取超时。
- `latest_frame_at=null` 表示还没有成功采集到画面。
- `source_fps=0` 表示实时画面不可用或摄像头断线。

### F-005 跌倒检测模型服务

步骤：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera/fall-detection/status
```

预期：

- `enabled=true`
- `running=true`
- `process_running=true`
- `speed_profile=accuracy`
- `accuracy_preserving=true`
- `last_error=null`

异常判定：

- `restart_count` 持续增加，说明模型不稳定。
- `last_error` 包含 RTSP timeout，说明模型读流异常。
- 进程命令行不能出现 `--analysis-width`、`--process-every 2`、`--half`，否则可能影响精度。

### F-006 跌倒事件转告警

步骤：

```powershell
Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/v1/camera/fall-detection/simulate
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/alarms?active_only=true"
```

预期：

- 生成 `fall_detected` 或 `fall_injury_risk`。
- 告警包含 `metadata.event`。
- 告警包含 `fall_score`、`injury.level`、`snapshot_path`。
- 前端全屏跌倒弹窗出现。

### F-007 跌倒告警解除闭环

步骤：

```powershell
Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/v1/alarms/fall/acknowledge-active
Start-Sleep -Seconds 5
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/alarms?active_only=true"
```

预期：

- 批量确认接口快速返回。
- 活动跌倒告警数量变为 0。
- 前端弹窗消失。
- 5 秒内不应因为同一场景马上再次弹出。

### F-008 截图读取

步骤：

1. 触发跌倒告警。
2. 从告警 `metadata.event.snapshot_path` 取得截图路径。
3. 访问 `/api/v1/camera/fall-detection/snapshot?path=...`。

预期：

- 返回 200 和 JPEG 图片。
- 非截图目录路径返回 403。
- 不存在文件返回 404。

### F-009 活动告警列表展示

步骤：

1. 触发跌倒告警。
2. 打开社区端页面。
3. 查看活动告警区域。

预期：

- 显示摄像头设备。
- 显示风险等级、置信度、伤情建议。
- 有截图时显示缩略图。
- 点击处理后列表同步减少。

## 6. 业务逻辑测试

### B-001 疑似跌倒不应过度报警

场景：

- 模型输出 `suspected_fall`，但 `fall_score` 较低，伤情等级为 `I0`。

预期：

- 可以作为观察状态记录。
- 不应持续制造高优先级弹窗。
- 不应短时间生成大量重复 `fall_injury_risk`。

### B-002 确认跌倒应强提醒

场景：

- `confirmed_fall`、`post_fall_monitoring`、`needs_assistance`、`emergency`。

预期：

- 进入活动告警。
- 高风险等级触发全屏弹窗。
- 显示人工处置建议。
- 可确认并闭环。

### B-003 告警去重与冷却

场景：

- 模型连续输出同一个 track 的多个状态变化。

预期：

- 不应每一帧都生成新告警。
- 人工确认后进入冷却期。
- 冷却期内不应反复弹出同一事件。

### B-004 多人场景

场景：

- 同画面中多人，只有一个人疑似跌倒。

预期：

- 告警应包含 `track_id`。
- 不同 `track_id` 可分别记录。
- 不能把所有人都显示为同一跌倒对象。

### B-005 恢复状态

场景：

- 跌倒后站起或恢复正常。

预期：

- 模型状态进入 `recovery_watch` 或 `recovered`。
- 系统可降低后续优先级。
- 已确认处理的旧告警不应重新变为活动状态。

## 7. 性能测试

### P-001 视频帧率

检查：

- `source_fps`
- `broadcast_fps`
- `latest_frame_size`
- 浏览器实际画面是否卡顿。

通过标准：

- 前端预览至少 10 FPS 以上为可用。
- 目标为 15 FPS 左右。
- 不能出现连续 10 秒以上黑屏。

### P-002 模型延迟

检查：

- 模型事件从动作发生到告警出现的时间。
- `camera_events.jsonl` 最后一行时间与前端弹窗时间差。

通过标准：

- 演示环境建议 3 秒内出现观察/疑似事件。
- 确认跌倒可接受几秒观察窗口，但不应超过业务规则设定。

### P-003 接口响应

检查接口：

```text
/camera/stream-status
/camera/fall-detection/status
/alarms?active_only=true
/alarms/fall/acknowledge-active
```

通过标准：

- 普通状态接口小于 1 秒。
- 批量确认接口小于 2 秒。
- 即使有多个浏览器 WebSocket，也不能长时间卡死。

### P-004 进程资源

检查：

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'backend.main:app|realtime_fall_monitor' }
```

通过标准：

- 一个后端进程。
- 一个跌倒模型进程。
- 没有重复模型进程抢摄像头。

## 8. 异常恢复测试

### R-001 摄像头断线

操作：

- 断开摄像头网络或关闭摄像头。

预期：

- `/camera/stream-status` 显示错误。
- 前端显示离线/读取失败状态。
- 模型 `last_error` 显示 RTSP 错误。
- 恢复网络后可以自动重连。

### R-002 模型进程被杀

操作：

```powershell
Stop-Process -Id <model_pid>
```

预期：

- 后端 supervisor 自动重启模型。
- `restart_count` 增加。
- 新 `pid` 出现。

### R-003 前端多开页面

操作：

- 同时打开多个社区端页面。

预期：

- 告警广播不卡死。
- 批量确认后所有页面最终同步消失。
- 断开的页面连接会被清理。

### R-004 截图文件丢失

操作：

- 删除某个告警截图。

预期：

- 前端显示截图缺失状态。
- 接口返回 404。
- 告警详情仍可展示文字信息。

## 9. 安全与隐私测试

### S-001 密码不入库不入仓

检查：

```powershell
git ls-files .env
rg "CAMERA_PASSWORD|实际摄像头密码" . --glob "!.env" --glob "!data/**" --glob "!logs/**"
```

预期：

- 真实密码只应存在本地 `.env` 或本机配置。
- 不应出现在文档、前端源码、日志输出、Git 提交内容中。

### S-002 截图路径保护

检查：

- 请求截图接口时传入截图目录外路径。

预期：

- 返回 403。
- 不能读取任意本地文件。

### S-003 医疗建议边界

预期：

- 系统可以提示“建议人工查看、联系照护人员、必要时呼叫急救”。
- 不应给出确定诊断或替代医生判断。

## 10. 前端体验测试

### U-001 正常监控态

预期：

- 页面首屏能看见监控入口。
- 摄像头状态、模型状态、帧率信息清晰。
- 没有无意义的大段说明占据主要空间。

### U-002 跌倒告警态

预期：

- 弹窗足够明显。
- 信息顺序符合处置逻辑：发生什么、在哪、严重程度、截图、该怎么做。
- 按钮文案明确。
- 点击确认后弹窗消失。

### U-003 异常态

预期：

- 摄像头不可达时显示明确错误。
- 模型离线时显示“跌倒检测离线/启动中/错误”。
- 不应用“在线”掩盖失败。

## 11. 当前已知重点风险

- 摄像头画面角度可能把窗帘、天花板边缘或局部人体误识别为跌倒，需要 ROI 区域或现场数据校准。
- 同一画面持续输出跌倒状态时，必须依赖去重和确认冷却，否则会反复弹窗。
- 多浏览器连接如果不设发送超时，会拖慢告警确认接口。
- 前端视频预览和模型同时抢主码流时，可能导致 RTSP 超时，应保持预览与模型分流。

## 12. 本轮测试记录模板

```text
测试时间：
测试人员：
后端 PID：
模型 PID：
摄像头状态：
视频流 FPS：
跌倒检测状态：
活动告警数量：
模拟跌倒结果：
确认处理结果：
发现问题：
处理结论：
```
