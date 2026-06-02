# 视频流稳定性与性能优化作战手册

## 1. 项目目标

当前项目不是从零设计的新系统，而是一个已经运行中的智慧养老视觉系统。现有能力已经覆盖：

- FastAPI Vision Service
- RTSP 双流（`main / analysis`）
- OpenCV / FFmpeg 拉流
- YOLO 人体检测
- YOLO Pose
- tracking
- WebRTC 视频播放
- WebSocket / overlay 结果展示
- 跌倒识别链路
- 前后端页面

当前核心问题不是“没有功能”，而是“整条实时视频链路不够稳定、不够流畅、不够同步”。

整个项目后续优化只围绕一个目标：

```text
先让视频像视频，再让 AI 像 AI。
```

当前第一优先级：

```text
不卡
不黑
不延迟三十秒
```

## 2. 当前已知事实

当前系统已经具备完整的实时视频与视觉推理闭环，但整体表现仍处于“可运行、未收敛”的状态。

典型运行态现象包括：

- `RTSP` 双流可以工作，但主流/分析流稳定性不一致。
- `main` 与 `analysis` 之间存在 fallback 机制。
- `detect / tracking / publish` 链路通常可运行，但不总是稳定达标。
- `pose` 链路可运行，但频率和观感远未达到最终目标。
- 前端曾出现：
  - 黑屏
  - reconnect
  - `Video FPS` 过低
  - 长延迟
  - YOLO 框比视频更新
  - 骨架不稳定显示
- 已经确认过：
  - 前端输入框与后端真实 RTSP 来源曾经不一致
  - `Clash/TUN` 会干扰局域网 RTSP 会话
  - `capture_process_open_start` 后可能出现 open 阶段阻塞或 `open_failed`

当前项目的工程主线必须从“局域网与采集稳定性”开始，而不是继续优先卷模型或告警逻辑。

## 3. 已知风险

当前明确已知的风险包括：

- 摄像头地址、端口、通道可能漂移
- 摄像头会话数可能被占满
- `Clash/TUN` 可能接管局域网 RTSP 会话
- `main` 码流比 `analysis` 更重，更容易不稳定
- 采集、渲染、推理问题容易互相伪装
- 前端现象可能与后端真实状态分裂
- 单次恢复成功不代表连续运行稳定

这些风险决定了后续优化必须严格分阶段推进，不能跨层乱跳。

## 4. P0 ~ P5 路线

### P0 网络与摄像头基线

当前目标：

- 固定可用摄像头地址
- 固定 `main / analysis` 对应通道
- 确保本机到摄像头的真实路径不经过 `Clash/TUN`
- 确认前端输入能真实切换后端双流

修改范围：

- 摄像头地址与通道
- 系统网络路径
- `Clash/TUN` 旁路
- 启动环境变量
- 设备重启与会话释放流程

不允许改什么：

- 模型
- pose 判定
- Temporal
- FallStateMachine
- 告警链路
- 前端渲染逻辑

关键指标：

- `RTSP OPTIONS` 是否可响应
- `cv2.VideoCapture(..., CAP_FFMPEG)` 是否 `opened=True`
- 本地 `SourceAddress` 是否为真实 `WLAN/LAN`
- `/status` 中 `main / analysis` 地址是否和预期一致

验收标准：

- 固定一组可用摄像头地址
- `main / analysis` 都能独立打开
- 前端输入修改后，后端真实地址同步切换

常见失败原因：

- `Clash/TUN` 仍在接管局域网 TCP
- 摄像头端口或通道变更
- 摄像头连接数上限
- 残留会话未释放
- 误把前端输入框当成真实运行地址

### P1 RTSP 采集稳定

当前目标：

- `main / analysis` 都能稳定 `open_ok -> first_frame_ok`
- 持续稳定出帧
- 不黑、不抖、不反复 `open_failed`

修改范围：

- `capture_process`
- `subprocess_capture_worker`
- OpenCV/FFmpeg 打开参数
- open/read 超时
- 采集 watchdog 与重启节流

不允许改什么：

- detect / pose 业务逻辑
- 前端功能
- 跌倒识别链路

关键指标：

- `capture_process_open_ok`
- `capture_process_first_frame_ok`
- `capture_fps`
- `source_fps`
- `frame_age_ms`
- `restart_count`

验收标准：

- `main / analysis` 连续 5 分钟保持 `connected`
- `capture_fps / source_fps` 持续非零
- `frame_age_ms` 不长期飙升
- 无 restart storm

常见失败原因：

- OpenCV open 卡死
- 首帧前没有硬超时
- 主码流太重
- 摄像头双流本身不稳定
- watchdog 过度重启

### P2 前端低延迟播放

当前目标：

- 前端只播放最新帧
- 不再持续播放旧帧
- 把视频延迟压到 `1~3 秒`

修改范围：

- `FrameBuffer` 最新帧策略
- WebRTC track 发送节奏
- 前端视频播放恢复
- 前端帧队列
- 重型原始 JSON 默认关闭

不允许改什么：

- 模型
- pose 业务逻辑
- 跌倒判定
- 告警链路

关键指标：

- `Video FPS`
- `Video Frames`
- 黑屏时长
- 端到端延迟
- `streamState`

验收标准：

- `Video FPS` 稳定 `8~10`
- 延迟降到 `1~3s`
- 不再出现持续播放历史帧
- 黑屏仅允许短暂恢复态存在

常见失败原因：

- WebRTC 反复推旧帧
- 浏览器未真正 `play()`
- 页面持续渲染重型原始 JSON
- 展示流本身不稳定

### P3 Overlay 同步

当前目标：

- YOLO 框、风险状态、骨架与当前视频同步
- 不再出现“框比画面新”

修改范围：

- WebSocket 最新结果策略
- overlay 绘制节奏
- `display_source / analysis_source` 对齐
- 坐标映射
- 前后端来源一致性显示

不允许改什么：

- 检测模型
- 姿态模型
- 状态机
- 告警 payload

关键指标：

- `WS FPS`
- `Overlay FPS`
- `Overlay Age`
- `detection_to_publish_lag_ms`

验收标准：

- YOLO 框与人物基本同步
- `Overlay Age` 平均 `< 300ms`
- 不再出现明显“框比视频快一拍”

常见失败原因：

- WS 消息排队
- overlay 用最新结果画在旧视频上
- display / analysis 坐标源混淆
- 页面显示地址和真实运行地址分裂

### P4 调度与性能稳定

当前目标：

- detect、tracking、publish 稳定达标
- 互不拖累
- 系统整体进入可连续运行状态

修改范围：

- `DETECTION_INTERVAL_MS`
- `YOLO_IMGSZ`
- worker cadence
- `inference_guard`
- pose skip 策略
- 状态指标补齐

不允许改什么：

- YOLO 模型本身
- TensorRT / ONNX
- Temporal
- FallStateMachine
- 告警链路

关键指标：

- `detection_worker_fps`
- `tracking_worker_fps`
- `result_publish_fps`
- `lock_wait_ms`
- `skipped_due_to_busy`
- CPU / GPU 利用率

验收标准：

- `detect >= 8`
- `tracking >= 10`
- `publish >= 9`
- 整机不卡死
- GPU 利用率提升但不过载

常见失败原因：

- pose 阻塞 detect
- 调度过激导致采集/推理互相拖垮
- 锁忙统计缺失

### P5 Pose 观感优化

当前目标：

- 先稳定非零
- 再把骨架观感提升到 `2~5 fps`
- 不以追 `10 fps` 为第一目标

修改范围：

- pose cadence
- target / fallback 条件
- frontend smoothing / interpolation
- 骨架显示策略

不允许改什么：

- 上云
- TensorRT / ONNX
- 跌倒阈值
- 状态机
- 告警逻辑

关键指标：

- `pose_fps`
- `pose_success`
- `pose_skip_reasons`
- 骨架空白时长
- 主观流畅度

验收标准：

- 有人场景下 `pose_success` 持续非零
- 骨架不长期断
- detect / tracking 不因 pose 恶化

常见失败原因：

- 追高频导致拖慢主链
- target 条件过严
- `inference_lock_busy`
- 骨架画在错误帧上

## 5. 当前明确不优先做的事

- 上云
- TensorRT
- ONNX
- 跌倒阈值优化
- 告警链路优化
- `FallStateMachine` 改造
- `Temporal` 逻辑改造
- 追 `pose 10fps`
- 重写播放器
- 推翻现有双流架构

## 6. 版本冻结 / 基线环境

每轮验收前必须固定并记录：

- 当前 RTSP 地址
- 摄像头 `main / analysis` 对应通道
- 当前 conda 环境
- Python 版本
- OpenCV 版本
- FFmpeg 版本或 OpenCV FFMPEG backend 信息
- 前端 commit / 后端 commit
- 是否开启 `Clash / TUN / 代理`
- 当前关键环境变量
  - `YOLO_IMGSZ`
  - `DETECTION_INTERVAL_MS`
  - `POSE_FPS`
  - `WEBRTC_VIDEO_FPS`
  - 其他当轮关键参数

目的：

- 防止“同一个问题，其实在不同环境下测出来”
- 防止今天能复现、明天不能复现

## 7. 验收采样时长

每阶段验收最少采样时长固定：

- `P0 / P1`：至少连续 `5 分钟`
- `P2 / P3`：至少连续 `3 分钟` 真人画面
- `P4 / P5`：至少 `站立 3 分钟 + 走动 3 分钟`

目的：

- 防止“刚连上十秒就误判稳定”
- 实时视频系统必须验证连续运行能力

## 8. 失败不退化规则

跨阶段禁止乱跳，必须遵守：

- 如果 `P3 overlay` 不同步，不允许优先回头改模型
- 如果 `P5 pose` 不顺，不允许优先回头改采集，除非 `capture_fps / frame_age_ms` 明确异常
- 如果 `P2 Video FPS` 很低，不允许先怀疑 pose
- 如果 `P1 RTSP` 还不稳定，不允许直接进入前端体验优化

目的：

- 保持定位链路单向收敛
- 防止“今天查前端，明天查模型，后天又回摄像头”

## 9. 展示流 / 分析流边界

双流职责必须明确：

- `main = 前端显示优先`
- `analysis = AI 分析优先`

允许的例外：

- 如果 `main` 卡顿或 stale，可临时允许 `analysis fallback` 作为展示流

但必须满足：

- 页面明确标注当前 `display_source`
- `/status` 明确给出 `display_source_current`
- 所有截图、录屏、验收必须说明当时显示的是 `main` 还是 `analysis`

目的：

- 防止前端看到的是 analysis，却误以为是 main
- 防止 overlay 坐标和显示流来源混淆

## 10. 最终演示标准

正式演示前，必须同时满足：

- 画面连续不卡
- 端到端延迟 `1~3 秒`
- YOLO 框与视频基本同步
- pose 有稳定显示
- `/status` 中无 `camera_lost`
- 前端显示 RTSP 与后端真实 RTSP 一致
- `stream_state` 不长期处于 `connecting / reconnecting`
- `Video FPS`、`Detect FPS`、`Track FPS` 达到最低可接受线

建议最低演示线：

- `Video FPS >= 8`
- `Detect FPS >= 8`
- `Track FPS >= 9~10`
- `Publish FPS >= 9`
- `pose` 稳定非零且肉眼可见

## 11. 单一事实源（Single Source of Truth）

所有运行态判断必须以 `/status` 为准。

禁止：

- 以前端输入框内容判断当前 RTSP 来源
- 以页面文本主观判断当前实际运行地址
- 以“我记得刚才切过了”判断当前配置
- 以浏览器单帧现象替代后端运行态

必须：

- `/status` 返回当前真实运行信息
- 至少包含：
  - `main_rtsp_url` 或等价真实主流来源
  - `analysis_rtsp_url` 或等价真实分析流来源
  - `display_source_current`
  - `stream_state`
- 前端页面中的“当前来源”必须来自 `/status`
- 所有验收截图必须包含 `/status` 关键字段或对应页面映射字段

目的：

- 避免“假现象调试”
- 避免 UI 和后端状态分裂
- 避免调了半天其实在看旧配置

## 12. 性能预算（Performance Budget）

每条链路必须有预算，不允许只说“感觉卡”。

建议端到端预算：

- RTSP capture：`<= 300ms`
- decode：`<= 100ms`
- detect + tracking：`<= 150ms`
- pose：`<= 200ms`
- publish：`<= 100ms`
- frontend render：`<= 200ms`

总预算：

- 正常目标：`<= 1~3s`

快速判定规则：

- 任意单模块连续超过 `500ms`，必须标记为 `bottleneck`
- 任意链路阶段出现持续排队或 backlog，优先当性能故障处理
- 不允许只看平均值，必须至少看 `avg + P95 + max`

目的：

- 快速定位谁拖慢整条链路
- 避免“系统很卡”但不知道卡在哪
- 让优化顺序可量化

## 13. 变更控制（Change Control）

每个阶段只允许围绕一个目标方向修改，不允许顺手跨层乱改。

原则：

- 一次只允许一个目标方向的改动
- 一个阶段内，优先控制在同一层内收敛
- 不允许“为了修 A，顺手改 B、C、D”

例如：

`P2 前端低延迟阶段`

允许：

- WebRTC
- FrameBuffer
- 前端渲染
- overlay 更新策略

禁止：

- 同时改 detect cadence
- 同时改 pose 逻辑
- 同时改 capture timeout
- 同时改跌倒判定

如果必须跨层改：

必须先记录：

- 为什么跨层
- 改哪些文件
- 预期影响
- 验收指标
- 回滚方式

目的：

- 避免“改一堆，然后不知道是谁修好的”
- 让每轮结论可复现
- 让回滚真正可执行

## 结语

这份文档不是“建议列表”，而是当前项目视频系统的工程作战手册。

执行顺序必须固定：

```text
网络 / 摄像头基线
→ RTSP 采集稳定
→ 前端低延迟播放
→ YOLO 框与画面同步
→ detect / tracking / publish 稳定
→ 最后再优化 pose 骨架观感
```

最终原则只有一句：

```text
先让视频像视频，再让 AI 像 AI。
```
