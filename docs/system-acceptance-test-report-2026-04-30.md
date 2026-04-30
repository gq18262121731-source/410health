# 系统验收测试记录

测试日期：2026-04-30
测试范围：后端服务、前端服务、摄像头实时流、跌倒检测服务、告警生成与解除、安全检查。

## 1. 测试结论

当前系统核心链路已经可运行：

- 后端服务在线。
- 前端服务在线。
- 摄像头可达。
- 视频流恢复到约 14.55 FPS。
- 跌倒模型在线，且保持 `accuracy` 精度优先。
- 模拟跌倒可以生成系统告警。
- 批量确认后活动跌倒告警可清零。
- 截图接口能拦截非法本地路径。

本轮测试发现并修复了两个关键问题：

- 跌倒告警洪泛：同一摄像头同一场景会产生大量活动告警。
- 告警解除不符合直觉：确认一条后下一条马上顶上来，看起来像弹窗没有消失。

已采取修复：

- 同一摄像头同一时间只保留一个活动跌倒告警。
- 新增 `POST /api/v1/alarms/fall/acknowledge-active` 批量确认接口。
- 前端确认按钮改为批量解除当前跌倒告警。
- 人工确认后加入 60 秒冷却。
- WebSocket 广播增加发送超时和并发发送，避免断开的浏览器拖慢确认链路。

## 2. 当前运行状态

后端端口：

```text
8000 online
```

前端端口：

```text
5173 online
```

进程状态：

```text
backend.main:app              1 个
realtime_fall_monitor.py      1 个
```

跌倒模型状态：

```text
enabled=true
running=true
process_running=true
speed_profile=accuracy
accuracy_preserving=true
last_error=null
```

摄像头状态：

```text
configured=true
online=true
ip=192.168.8.253
port=10554
error=null
```

视频流状态：

```text
running=true
profile=smooth
source_fps≈14.55
last_error=null
active_url=rtsp://admin:***@192.168.8.253:10554/tcp/av0_1
```

模型使用主码流：

```text
rtsp://admin:***@192.168.8.253:10554/tcp/av0_0
```

## 3. 自动化测试记录

### T-001 后端与前端端口

结果：通过

```text
8000 端口监听正常
5173 端口监听正常
```

### T-002 摄像头在线检测

结果：通过

```text
configured=true
online=true
latency_ms≈14.05
error=null
```

### T-003 实时视频流

结果：通过

```text
running=true
keep_warm=true
latest_frame_at 有值
source_fps≈14.55
last_error=null
```

说明：前端预览使用辅码流 `av0_1`，用于稳定浏览器展示；跌倒模型继续使用主码流 `av0_0`，不降低检测精度。

### T-004 跌倒检测服务

结果：通过

```text
process_running=true
accuracy_preserving=true
restart_count=0
```

### T-005 模拟跌倒告警

结果：通过

输入：

```text
POST /api/v1/camera/fall-detection/simulate
```

结果：

```text
afterSimFallCount=1
alarm_type=fall_injury_risk
alarm_level=CRITICAL
snapshot_path 已生成
```

### T-006 批量确认跌倒告警

结果：功能通过，性能需继续观察

输入：

```text
POST /api/v1/alarms/fall/acknowledge-active
```

结果：

```text
acknowledged_count=1
afterAckFallCount=0
```

观察：

- 无活动告警时接口约 0.15 秒返回。
- 有活动告警且浏览器连接较多时，曾观察到约 4.1 秒返回。
- 前端已先本地移除弹窗，因此用户侧会立即看到弹窗消失。
- 后端已增加 WebSocket 并发发送与短超时，后续还应在多浏览器真实场景复测。

### T-007 截图接口路径保护

结果：通过

输入：

```text
/api/v1/camera/fall-detection/snapshot?path=C:\Windows\win.ini
```

结果：

```text
403
```

### T-008 明文密码检查

结果：通过

检查范围排除了本地 `.env`、`logs/`、`data/`、`Camera/`。

```text
未在代码和文档中发现真实密码明文。
```

## 4. 发现的问题与处理状态

### P0 已修复：跌倒弹窗确认后不消失

原因：

```text
活动跌倒告警有多条，旧逻辑只确认第一条。
```

修复：

```text
前端批量确认 + 后端批量接口 + 告警冷却。
```

状态：

```text
已修复并验证 afterAckFallCount=0。
```

### P0 已修复：跌倒告警洪泛

原因：

```text
模型在同一摄像头场景持续输出多个 track / 多状态事件，后端全部入队。
```

修复：

```text
同一摄像头只保留一个活动跌倒告警，等待人工确认。
```

状态：

```text
已修复。
```

### P1 需继续优化：当前场景可能误识别为跌倒

现象：

```text
摄像头当前画面中，模型持续输出 post_fall_monitoring / fall_injury_risk。
```

判断：

```text
这可能是摄像头角度、画面边缘、窗帘或局部人体框造成的场景误报。
```

建议：

- 增加 ROI 区域，仅检测老人主要活动区域。
- 排除天花板、窗帘、强光窗口等区域。
- 用当前摄像头采集正常样本做阈值校准。
- 将 `suspected_fall` 仅作为观察状态，不进入高优先级告警。

### P2 需复测：多浏览器下确认接口耗时

现象：

```text
有活动告警并存在多个 WebSocket 连接时，批量确认曾耗时约 4.1 秒。
```

已处理：

```text
WebSocket 广播改为并发发送，并加 0.2 秒发送超时。
```

建议：

```text
关闭多余浏览器标签后，再执行 5 次批量确认耗时测试。
```

## 5. 下一轮建议测试

1. 在摄像头真实场景下做 ROI 配置测试。
2. 用 5 段正常活动视频和 5 段模拟跌倒视频做事件级准确率测试。
3. 连续运行 30 分钟，记录 `restart_count`、`source_fps`、活动告警数量。
4. 多开 3 个前端页面，重复触发和解除跌倒告警，确认所有页面同步消失。
5. 模型进程被杀后验证自动重启。
6. 摄像头断线后验证前端错误提示和恢复能力。
