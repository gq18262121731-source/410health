# 智慧康养项目移动端开发指南

适用范围: 本仓库移动端开发、方案评审、AI 编程助手协作  
文档定位: 基于当前代码现状的 MVP 开发指南  
主线技术栈: Flutter  
最后校准时间: 2026-03-25

## 1. 文档目的

这份文档不再是通用移动端模板，而是针对当前仓库真实结构整理出的移动端开发指南。目标是让开发者或 AI 助手在进入 `mobile/` 目录前，先明确三件事：

1. 当前项目已经有什么，不需要重新发明。
2. 当前移动端真正应该对接哪些后端能力。
3. 第一阶段应该先把什么做完，而不是把未来规划写成既成事实。

本文默认移动端以 Flutter 为正式主线，现有 Web 端 Vue 3 实现主要作为接口契约和交互参考，不作为移动端技术路线。

## 2. 项目架构校准

### 2.1 当前仓库的真实结构

当前项目不是单一 App，而是一个 AIoT 康养监护系统，主链路如下：

```text
iot 设备/串口/MQTT
  -> backend (FastAPI + service layer + ML/analysis)
  -> HTTP API / WebSocket
  -> frontend/vue-dashboard (社区/家属 Web 端)
  -> mobile/flutter_app (移动端样例工程)
```

关键目录说明：

- `backend/`: FastAPI 后端，已经提供认证、设备、健康数据、照护、告警、聊天/报告、语音等接口。
- `frontend/vue-dashboard/`: Vue 3 Web 管理端，已经实现登录、社区总览、家属视图、设备视图、Agent 工作台等页面。
- `mobile/flutter_app/`: Flutter 移动端样例工程，当前只覆盖角色选择和实时健康卡片展示。
- `mobile/android-snippets/`: Android 原生片段，属于能力参考，不是当前主应用代码。
- `iot/`: 串口、MQTT、手环数据接入层。

### 2.2 当前移动端结论

必须明确：

- 当前仓库里的移动端基础是 Flutter，不是 Vue + Capacitor。
- 文档、实现、评审都应围绕 `mobile/flutter_app` 演进。
- 现有 Flutter 工程还是 demo 级别，不能误判为已经具备完整移动端架构。

## 3. 当前系统已经具备的后端能力

移动端开发必须建立在现有接口之上，而不是重新假设一套产品后端。

### 3.1 认证与会话

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/mock-accounts`
- `POST /api/v1/auth/register/elder`
- `POST /api/v1/auth/register/family`
- `POST /api/v1/auth/register/community-staff`

当前登录响应模型以 `LoginResponse` 为准，包含：

- `token`
- `user`
- `expires_at`

当前会话用户模型以 `SessionUser` 为准，包含：

- `id`
- `username`
- `name`
- `role`
- `community_id`
- `family_id`

### 3.2 设备与绑定

- `GET /api/v1/devices`
- `GET /api/v1/devices/{mac_address}`
- `POST /api/v1/devices/register`
- `POST /api/v1/devices/bind`
- `POST /api/v1/devices/unbind`
- `POST /api/v1/devices/rebind`
- `GET /api/v1/devices/{mac_address}/bind-logs`

核心移动端依赖模型：

- `DeviceRecord`
- `DeviceBindLogRecord`

### 3.3 健康实时数据与历史数据

- `GET /api/v1/health/realtime/{device_mac}`
- `GET /api/v1/health/trend/{device_mac}`
- `GET /api/v1/health/devices/{device_mac}/history`
- `POST /api/v1/health/score`
- `POST /api/v1/health/warning/check`

核心移动端依赖模型：

- `HealthSample`
- `HealthTrendPoint`
- `DeviceHistoryResponse`

其中 `HealthSample` 当前真实字段包括：

- `device_mac`
- `timestamp`
- `heart_rate`
- `temperature`
- `blood_oxygen`
- `blood_pressure`
- `battery`
- `sos_flag`
- `source`
- `device_uuid`
- `ambient_temperature`
- `surface_temperature`
- `steps`
- `packet_type`
- `sos_value`
- `sos_trigger`
- `anomaly_score`
- `health_score`

### 3.4 告警与移动端通知数据

- `GET /api/v1/alarms`
- `GET /api/v1/alarms/queue`
- `GET /api/v1/alarms/queue/snapshot`
- `GET /api/v1/alarms/mobile-pushes`
- `POST /api/v1/alarms/{alarm_id}/acknowledge`

核心移动端依赖模型：

- `AlarmRecord`
- `AlarmQueueItem`
- `MobilePushRecord`

### 3.5 家属/照护访问画像

- `GET /api/v1/care/access-profile/me`
- `GET /api/v1/care/directory`
- `GET /api/v1/care/directory/family/{family_id}`
- `GET /api/v1/care/community/dashboard`

家属端 MVP 最重要的接口不是“设备列表”本身，而是 `CareAccessProfile`。它直接告诉移动端：

- 当前用户是否已绑定
- 当前角色能看哪些设备
- 当前有哪些健康评估摘要
- 当前有哪些健康报告摘要
- 当前是否具备查看指标、评估、报告的权限

### 3.6 语音能力

- `GET /api/v1/voice/status`
- `POST /api/v1/voice/asr`
- `POST /api/v1/voice/tts`

语音能力当前依赖后端配置。若 `.env` 中未设置 `QWEN_API_KEY`，移动端必须降级，不应假设语音必然可用。

### 3.7 WebSocket 实时链路

- `GET /ws/health/{device_mac}` WebSocket
- `GET /ws/alarms` WebSocket

移动端实时策略必须写死为：

1. 进入页面先拉取 REST 快照。
2. 页面驻留后订阅设备实时 WebSocket。
3. 告警中心订阅告警 WebSocket。
4. WebSocket 断开后自动重连。

## 4. 角色范围与移动端优先级

当前系统代码支持的角色包括：

- `family`
- `elder`
- `community`
- `admin`

但移动端第一阶段不要同时铺开所有角色。建议优先级如下：

### 4.1 第一阶段主目标

家属端 `family` 作为移动端 MVP 主视角。

原因：

- Web 端已经有较完整的家属视图和照护访问模型，可直接映射。
- `CareAccessProfile` 已能提供家属端大部分页面所需的聚合信息。
- 移动端天然更适合家属随时查看老人状态、接收告警、查看报告。

### 4.2 第二阶段扩展

- `elder`: 语音问答、语音播报、大按钮模式。
- `community`: 只建议做轻量值班视图，不建议第一阶段照搬完整社区工作台。

### 4.3 本文约束

除非明确标注为“后续规划”，否则本文提到的移动端能力都必须能映射到当前仓库已有接口。

## 5. 当前 Flutter 工程现状评估

目录：`mobile/flutter_app`

当前已有内容：

- `main.dart`: 应用入口。
- `screens/role_selector_screen.dart`: 角色选择页。
- `screens/dashboard_screen.dart`: 仪表盘页。
- `services/api_service.dart`: 简单 HTTP/WebSocket 调用。
- `models/health_sample.dart`: 实时健康样本模型。
- `widgets/vital_card.dart`: 健康卡片组件。

当前已实现能力：

- 选择角色入口
- 拉取设备列表
- 拉取单设备实时快照
- 订阅单设备实时 WebSocket
- 展示心率、体温、血氧、血压、SOS 状态

当前缺失的关键能力：

- 登录与 Token 持久化
- 基于 `auth/me` 的会话恢复
- 家属与老人绑定关系处理
- 基于 `CareAccessProfile` 的页面初始化
- 历史趋势与聚合历史页面
- 告警列表、告警确认、告警队列
- 正式健康报告摘要
- 语音可用性判断、ASR、TTS
- 错误态、空态、弱网重试
- 模块化的 repository / session / state 管理层

结论：

当前 Flutter 工程应视为“技术验证样例”，不是“已完成的移动端应用”。后续开发应在保留现有实时展示经验的前提下，重构为正式 MVP 工程结构。

## 6. 移动端推荐架构

Flutter 端建议按以下模块收敛，不再继续把所有逻辑堆在单一页面中。

### 6.1 模块划分

#### app shell / navigation

职责：

- 应用入口
- 路由与页面栈管理
- 登录态切换
- 全局错误页/空页/加载页

#### auth

职责：

- 登录
- Token 存储
- 会话恢复
- 当前用户读取
- 鉴权失效处理

依赖接口：

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

#### devices & binding

职责：

- 展示当前用户可访问设备
- 展示绑定状态
- 必要时支持绑定/解绑/改绑入口

依赖接口：

- `GET /api/v1/care/access-profile/me`
- `GET /api/v1/devices`
- `POST /api/v1/devices/bind`
- `POST /api/v1/devices/unbind`
- `POST /api/v1/devices/rebind`

#### realtime monitoring

职责：

- 当前设备快照展示
- 实时指标刷新
- SOS 与健康分即时态展示

依赖接口：

- `GET /api/v1/health/realtime/{device_mac}`
- `GET /ws/health/{device_mac}`

#### history & report

职责：

- 历史趋势
- 聚合历史
- 健康评估摘要
- 健康报告摘要

依赖接口：

- `GET /api/v1/health/trend/{device_mac}`
- `GET /api/v1/health/devices/{device_mac}/history`
- `GET /api/v1/care/access-profile/me`
- `POST /api/v1/chat/report/device`

#### alarm center

职责：

- 活动告警列表
- 告警队列
- 告警确认
- 移动端通知记录查看

依赖接口：

- `GET /api/v1/alarms`
- `GET /api/v1/alarms/queue`
- `GET /api/v1/alarms/mobile-pushes`
- `POST /api/v1/alarms/{alarm_id}/acknowledge`
- `GET /ws/alarms`

#### voice

职责：

- 语音能力检测
- 上传录音做 ASR
- 文本转语音播放

依赖接口：

- `GET /api/v1/voice/status`
- `POST /api/v1/voice/asr`
- `POST /api/v1/voice/tts`

#### session & api client

职责：

- 统一 base URL 管理
- Bearer Token 注入
- 错误码映射
- 超时与重试
- WebSocket 生命周期管理

### 6.2 通信规范

- REST: 用于登录、初始化、快照、历史、报告、告警操作。
- WebSocket: 用于设备实时监测和告警推送。
- 不要反过来。初始化数据不能依赖 WebSocket 首包。

### 6.3 推荐数据流

#### 设备实时页

```text
进入页面
  -> GET /care/access-profile/me
  -> 选出默认设备
  -> GET /health/realtime/{mac}
  -> 建立 ws/health/{mac}
  -> 持续更新页面状态
```

#### 告警中心

```text
进入页面
  -> GET /alarms?active_only=true
  -> GET /alarms/queue
  -> 建立 ws/alarms
  -> 用户确认告警
  -> POST /alarms/{alarm_id}/acknowledge
```

#### 语音页

```text
进入页面
  -> GET /voice/status
  -> configured = false 时显示不可用态
  -> configured = true 时开放录音与播报
```

## 7. 移动端 MVP 页面范围

第一阶段页面范围建议固定为以下 6 类。

### 7.1 登录页

目标：

- 用户账号密码登录
- 登录失败提示
- 登录成功后恢复 `SessionUser`

不纳入当前阶段：

- 短信验证码
- 生物识别登录
- 多因素认证

### 7.2 家属首页

目标：

- 读取 `CareAccessProfile`
- 展示当前绑定状态
- 展示当前可访问设备列表
- 选择默认关注设备

### 7.3 设备实时监测页

目标：

- 显示 `HealthSample`
- 支持自动刷新与 WebSocket 实时更新
- 明确展示心率、血氧、体温、血压、电量、SOS、健康分

### 7.4 历史趋势与报告页

目标：

- 使用 `trend` 展示短时曲线
- 使用 `history` 展示日/周聚合历史
- 使用 `CareAccessProfile.health_reports` 展示报告摘要

### 7.5 告警中心

目标：

- 展示活动告警
- 展示队列优先级
- 支持确认告警
- 支持展示最近移动端推送记录

### 7.6 语音页

目标：

- 检查语音是否已启用
- 启用后支持上传录音转文字
- 启用后支持文字播报

说明：

该页属于 MVP 边缘功能，可排在告警中心之后，不得阻塞基础监测链路交付。

## 8. 标准接口与模型契约

移动端文档中应以下列模型作为标准依赖面。

### 8.1 `LoginResponse`

```json
{
  "token": "string",
  "user": {
    "id": "string",
    "username": "string",
    "name": "string",
    "role": "family",
    "community_id": "string",
    "family_id": "string"
  },
  "expires_at": "2026-03-25T12:00:00Z"
}
```

### 8.2 `DeviceRecord`

移动端至少关注这些字段：

- `mac_address`
- `device_name`
- `model_code`
- `ingest_mode`
- `user_id`
- `status`
- `activation_state`
- `bind_status`
- `last_seen_at`
- `last_packet_type`

### 8.3 `HealthSample`

移动端展示层至少消费这些字段：

- `device_mac`
- `timestamp`
- `heart_rate`
- `temperature`
- `blood_oxygen`
- `blood_pressure`
- `battery`
- `sos_flag`
- `steps`
- `health_score`

### 8.4 `CareAccessProfile`

移动端初始化必须关注：

- `binding_state`
- `bound_device_macs`
- `related_elder_ids`
- `capabilities`
- `basic_advice`
- `device_metrics`
- `health_evaluations`
- `health_reports`

### 8.5 `AlarmRecord`

移动端告警页至少消费：

- `id`
- `device_mac`
- `alarm_type`
- `alarm_level`
- `alarm_layer`
- `message`
- `created_at`
- `acknowledged`
- `anomaly_probability`

### 8.6 `DeviceHistoryResponse`

移动端历史页必须支持：

- `window = day | week`
- `bucket = raw | hour | day`
- `points[]`

每个 `points` 元素至少处理：

- `bucket_start`
- `bucket_end`
- `heart_rate`
- `temperature`
- `blood_oxygen`
- `health_score`
- `battery`
- `steps`
- `sos_count`
- `sample_count`
- `risk_level`

## 9. 开发顺序

移动端开发顺序固定如下，后续执行时不要再重新排序。

### 第 1 步: 登录与会话恢复

必须完成：

- 登录表单
- Token 持久化
- 冷启动调用 `auth/me`
- 401 自动清理本地会话

交付标准：

- App 重启后能恢复登录态
- 会话失效时能回到登录页

### 第 2 步: 家属访问画像与绑定设备列表

必须完成：

- 调用 `care/access-profile/me`
- 显示绑定状态
- 显示用户可访问设备
- 选择默认设备

交付标准：

- 未绑定用户有空态与引导文案
- 已绑定用户能进入设备详情链路

### 第 3 步: 设备实时监测页

必须完成：

- REST 快照
- `ws/health/{mac}` 实时更新
- 心率、血氧、体温、血压、电量、SOS 展示

交付标准：

- 页面首次进入不依赖 WebSocket 首包
- WebSocket 断开后可恢复

### 第 4 步: 历史趋势与报告摘要

必须完成：

- `trend` 曲线
- `history` 聚合历史
- `health_reports` 摘要展示

交付标准：

- 支持至少日视图和周视图
- 空数据时显示空态，不报错

### 第 5 步: 告警中心与告警确认

必须完成：

- 活动告警列表
- 队列列表
- 告警确认
- 告警 WebSocket 更新

交付标准：

- 用户可确认告警
- 页面能区分已确认/未确认状态

### 第 6 步: 语音能力接入

必须完成：

- `voice/status`
- ASR 上传
- TTS 播放
- 未配置语音时的降级态

交付标准：

- 后端未配置时不崩溃
- 后端已配置时能完成最小闭环

## 10. 非功能要求

### 10.1 可读性与老人场景约束

- 关键指标卡片必须大字号。
- 重要按钮触达面积不得过小。
- 告警态、正常态、等待态必须有明确视觉区分。

说明：

虽然第一阶段主打家属端，但页面风格不能做得过于桌面化，后续 Elder 模式仍需复用一部分设计体系。

### 10.2 弱网与重连

- REST 请求失败时必须有用户可理解的错误文案。
- WebSocket 断开后必须自动重连。
- 页面不能把“暂无数据”和“请求失败”混为一谈。

推荐策略：

- REST: 超时 + 有限重试
- WebSocket: 指数退避重连

### 10.3 Token 持久化

- 必须持久化登录 Token。
- 每次冷启动先恢复 Token，再调用 `auth/me`。
- 认证失败后必须清理本地状态。

### 10.4 语音能力降级

- `voice/status.configured = false` 时，录音和播报入口必须禁用。
- 不允许前端直接假设 DashScope、Paraformer、CosyVoice 已经就绪。

### 10.5 不纳入当前阶段的能力

下列能力没有当前代码依据，不能写成现状：

- 短信验证码登录
- 生物识别登录
- 离线数据双向同步
- 原生推送完整集成
- Capacitor 打包方案
- 完整双端独立产品线

如果需要保留，只能放入“后续规划”。

## 11. 后续规划

以下内容可以保留为下一阶段方向，但不能作为当前移动端交付承诺：

- Elder 语音陪护模式
- 社区值班轻应用
- 原生推送接入
- 更完整的消息中心
- 多设备切换与家庭组视图
- Android 原生能力进一步融合 `android-snippets`

## 12. AI 助手协作要求

当使用 Cursor、Codex、Copilot 等 AI 助手参与移动端开发时，默认遵守以下约束：

1. 所有移动端实现优先参考 `mobile/flutter_app`，不是新建第二套移动端。
2. 接口字段以 `backend/models` 和 `frontend/vue-dashboard/src/api/client.ts` 为准。
3. 不得在未核对代码前擅自写入短信登录、Capacitor、原生推送等未落地能力。
4. 先完成家属端 MVP，再讨论老人端和社区端扩展。
5. 实时页必须采用“REST 快照 + WebSocket 持续更新”的组合策略。

## 13. 一句话结论

这个项目当前的移动端工作，不是重新设计一套“理想中的健康 App”，而是基于现有 FastAPI 后端、Vue 端接口契约和 Flutter 样例工程，把家属端监护 MVP 稳定地落出来。
