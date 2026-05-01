# 摄像头局域网对话 demo

这个 demo 按“先探测能力，再测试扬声器，最后做实时麦克风对讲”的顺序验证摄像头局域网对话链路。

## 结论先看

当前这台摄像头的 ONVIF/RTSP 探测结果是：

- ONVIF 暴露了 `device`、`media`、`events`、`ptz`、`imaging` 服务。
- RTSP 暴露了摄像头麦克风音轨，格式为 `PCMA/8000/1`。
- ONVIF `GetAudioOutputs`、`GetAudioOutputConfigurations`、`Receiver.GetReceivers` 不可用。
- RTSP `DESCRIBE` 接受了 backchannel `Require` 头，但 SDP 里没有真正的 backchannel 音频轨。

所以，这台设备不能直接用截图里的纯 ONVIF 标准接口完成“电脑麦克风 -> 摄像头扬声器”。实际可用链路是：

```text
Windows 麦克风/测试音 -> 32 位 PowerShell -> 厂商 LAN SDK DevDll_924.dll -> 摄像头扬声器
```

## 准备配置

`.env` 至少需要：

```env
CAMERA_IP=192.168.8.253
CAMERA_USER=admin
CAMERA_PASSWORD=你的摄像头密码
CAMERA_ONVIF_PORT=10080
CAMERA_RTSP_PORT=10554
CAMERA_STREAM_RTSP_PATH=/tcp/av0_1
CAMERA_LAN_TALK_DLL_DIR=C:\Program Files (x86)\IPCam ActiveX\924
```

如果没有设置 `CAMERA_LAN_TALK_DLL_DIR`，脚本默认使用 `C:\Program Files (x86)\IPCam ActiveX\924`。

## 运行

建议使用项目当前可用的 Python 环境：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_lan_dialog_demo.py probe
```

发送 3 秒测试音到摄像头扬声器：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_lan_dialog_demo.py tone --seconds 3
```

把 Windows 默认麦克风实时推到摄像头扬声器：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_lan_dialog_demo.py mic --seconds 10
```

如果机器有多个麦克风，可以指定 DirectShow 设备名：

```powershell
C:\Users\13010\anaconda3\envs\helth\python.exe scripts\camera_lan_dialog_demo.py mic --seconds 10 --audio-device "麦克风阵列 (Realtek(R) Audio)"
```

## 常见问题

- `imageio_ffmpeg is missing`：用了系统 `python`，请切到 `helth` 环境，或安装 `imageio-ffmpeg`。
- `DEV_DLL_924_NOT_FOUND`：安装厂商 ActiveX/SDK，或把 `CAMERA_LAN_TALK_DLL_DIR` 指到包含 `DevDll_924.dll` 的目录。
- `LAN talk gateway was not ready`：看 `logs/camera_lan_dialog_tone_<send-mode>.log` 或 `logs/camera_lan_dialog_mic_<send-mode>.log`，通常是 IP、端口、密码、DLL 位数不匹配。
- `talkRet=-1`：对讲通道已打开，但当前音频写入函数或编码模式不被设备接受。请逐个测试 `pcm_mode0`、`pcm_mode1`、`pcm_setdata`、`encoded_setdata`、`encoded_mode0`、`encoded_mode1`。
- 能监听摄像头声音但不能对讲：这是 ONVIF 能力不足导致的，需走厂商 SDK 或要求厂家提供标准 ONVIF backchannel 示例。
