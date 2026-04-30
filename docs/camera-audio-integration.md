# 摄像头音频与对讲接入更新记录

## 本次更新范围

本分支继续推进家属端摄像头能力，重点补充了摄像头监听、网页麦克风上行、厂商对讲通道探测和交接说明。视频流、截图、状态检测、云台控制仍沿用后端统一连接摄像头，再通过 WebSocket/HTTP 转发给前端的架构。

## 已完成能力

- 后端新增摄像头音频状态接口：`GET /api/v1/camera/audio/status`。
- 后端新增摄像头音频监听 WebSocket：`/ws/camera/audio/listen`，通过 RTSP 音频轨读取摄像头麦克风并转成 `pcm_s16le / 8000Hz / mono` 推给浏览器。
- 后端新增网页麦克风对讲 WebSocket：`/ws/camera/talk/web`，浏览器采集麦克风后转成 `pcm_s16le / 8000Hz / mono` 发给后端。
- 前端监控卡片新增“开始监听”和“局域网对讲”按钮，监听可直接播放摄像头侧声音，对讲会显示麦克风上行、网关接入和设备通道状态。
- 新增多组诊断脚本，方便后续继续验证厂商 SDK、ActiveX、ONVIF、RTSP backchannel 和实际帧率。

## 对讲当前结论

手机 App 可以对讲，说明摄像头硬件支持扬声器播放。但根据当前资料和自测结果，手机 App 使用的是厂商私有 P2P/VSNet SDK 通道，不是标准 ONVIF 对讲通道。

已确认的证据：

- Android Demo 使用 `PPPPStartTalk(deviceId)` 开启对讲。
- Android Demo 使用 `PPPPTalkAudioData(deviceId, data, len)` 持续发送麦克风音频。
- Android 麦克风采集格式是 `8000Hz / mono / PCM16`。
- iOS SDK 也暴露了 `startTalk` / `stopTalk`。
- WEB-SDK / ActiveX 目前只看到 `StartTalk()`、`StopTalk()`、`IsTalking`、`Listen`，没有看到可从后端主动注入 PCM/G711 音频数据的公开接口。
- ONVIF `GetServices` 只有 device、media、events、ptz、imaging。
- ONVIF `GetAudioOutputs` 和 `GetAudioOutputConfigurations` 不可用。
- RTSP SDP 只有普通视频轨和摄像头麦克风音频轨，没有明确的 ONVIF backchannel 反向音频轨。

因此，目前网页端对讲已经能做到“浏览器麦克风 -> Windows 后端”，但“Windows 后端 -> 摄像头扬声器”还缺厂商明确可用的音频写入接口。

## 新增后端接口

```text
GET  /api/v1/camera/audio/status
GET  /api/v1/camera/audio/stream-status
GET  /api/v1/camera/talk/status
POST /api/v1/camera/talk/start
POST /api/v1/camera/talk/stop
GET  /api/v1/camera/talk/web/status
POST /api/v1/camera/talk/web/stop
WS   /ws/camera/audio/listen
WS   /ws/camera/talk/web
```

## 新增配置项

```env
CAMERA_AUDIO_RTSP_PATH=/tcp/av0_0
CAMERA_AUDIO_SAMPLE_RATE=8000
CAMERA_SDK_DLL_DIR=
CAMERA_AUDIO_GATEWAY_URL=
CAMERA_ACTIVEX_CLSID=1E125331-B4E3-4EE3-B3C1-24AD1A3E5DEB
CAMERA_ACTIVEX_ID=
CAMERA_ACTIVEX_DEV_TYPE=924
CAMERA_ACTIVEX_PORT=10080
CAMERA_TALK_MAX_SECONDS=60
CAMERA_P2P_DLL_DIR=C:\Program Files (x86)\IPCam ActiveX\925
```

真实摄像头密码必须只放本地 `.env`，不要提交到 GitHub。

## 新增诊断脚本

```text
scripts/camera_audio_probe.py
scripts/camera_sdk_probe.py
scripts/camera_activex_probe.py
scripts/camera_activex_talk_bridge.ps1
scripts/camera_audio_gateway_32.py
scripts/camera_lan_talk_gateway.ps1
scripts/camera_listen_file_monitor.py
scripts/camera_onvif_talk_probe.py
scripts/camera_p2p_talk_gateway.ps1
scripts/camera_talk_mode_probe.py
```

常用命令：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_onvif_talk_probe.py
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_listen_file_monitor.py
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_talk_mode_probe.py
```

## 给后续同事的判断标准

- 如果只是要视频、云台、截图、状态检测：当前分支已经可用。
- 如果要监听摄像头麦克风：优先走 `/ws/camera/audio/listen`。
- 如果要网页麦克风对讲：前端和后端上行链路已搭好，但还需要厂商提供可用的 Windows/Python/C++ 对讲音频注入接口。
- 如果客服说 ONVIF 支持对讲：请让对方提供 `GetAudioOutputs` 成功返回，或提供带 `www.onvif.org/ver20/backchannel` 的 RTSP SDP 示例。
- 如果客服说用 SDK 对讲：请让对方提供 Windows 端最小 Demo，至少包含连接摄像头、开启对讲、发送 PCM/G711 音频、关闭对讲。
