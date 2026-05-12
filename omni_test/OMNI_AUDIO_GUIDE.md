# Qwen3.5-Omni-Plus 语音交互测试指南

## 📋 概述

本指南提供了测试 Qwen3.5-Omni-Plus 模型的脚本和说明。该模型支持：
- **文本输入** → 文本输出
- **文本输入** → 文本 + 语音输出  
- **语音输入** → 文本 + 语音输出
- **多模态交互** (同时处理文本和语音)

## ⚡ 两种实现方式

### 1. REST API 方式（HTTP）
- 依赖: `requests`, `httpx`
- 文件: `test_omni_audio.py`, `test_omni_quick.py`
- 特点: 简单直接，适合一次性请求
- ⚠️ 当前存在 403 权限问题（可能需要模型开通）

### 2. **WebSocket 实时方式（推荐）**
- 依赖: `dashscope` SDK (>= 1.23.9)
- 文件: `test_omni_realtime.py`, `test_omni_realtime_quick.py`
- 特点: 实时双向交互，低延迟，更优的用户体验
- ✅ 由官方 SDK 支持，更稳定可靠

## 🚀 快速开始

### 1. 安装 DashScope SDK（推荐方式）

```bash
# 安装最新版本（需要 >= 1.23.9）
pip install --upgrade dashscope

# 验证版本
python -c "import dashscope; print(dashscope.__version__)"
```

### 2. 检查环境配置

脚本自动从 `.env` 文件加载：

```
DASHSCOPE_API_KEY=sk-xxx  # 或 QWEN_API_KEY
```

### 3. 运行快速测试

```bash
# WebSocket 实时方式（推荐）
python test_omni_realtime_quick.py

# 如果上面失败，尝试 REST API 方式
python test_omni_quick.py
```

### 4. 运行完整测试

```bash
# WebSocket 实时交互
python test_omni_realtime.py

# REST API 模式
python test_omni_audio.py
```

## 📝 脚本说明

### WebSocket 实时方式（推荐）

#### `test_omni_realtime_quick.py` - 快速测试
- 最少依赖（仅需 dashscope SDK）
- 快速验证连接
- 测试文本 → 语音流程

```bash
python test_omni_realtime_quick.py
```

#### `test_omni_realtime.py` - 完整交互
- 支持多种测试模式
- 实时双向语音交互
- 自动保存输出音频
- 交互式对话模式

```bash
python test_omni_realtime.py

# 选项:
# 1. 文本输入 → 语音输出
# 2. 语音输入 → 语音输出
# 3. 交互模式（实时对话）
# 4. 退出
```

### REST API 方式（备选）

#### `test_omni_quick.py` - 快速测试
- 依赖少（仅需 requests）
- 测试基础连接和文本对话
- 适合快速验证 API 是否可用

```bash
python test_omni_quick.py
```

#### `test_omni_audio.py` - 完整功能
- 支持文本和语音输入
- 支持接收语音输出
- 自动保存响应音频为文件
- 包含详细的调试信息

```bash
python test_omni_audio.py

# 带语音输入的测试
# 将语音文件放在项目根目录，命名为 test_audio.wav
# 脚本会自动检测并测试
```

## 🎙️ 语音交互详解

### WebSocket 实时方式（推荐）

#### 1. 连接和会话配置

```python
from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
import dashscope

# 设置 API Key
dashscope.api_key = "sk-xxx"

# 创建回调处理器
class MyCallback(OmniRealtimeCallback):
    def on_open(self):
        print("连接已建立")
    
    def on_event(self, response):
        # 处理服务器事件
        event_type = response.get("type")
        if event_type == "response.audio_transcript.delta":
            print(f"收到文本: {response.get('delta')}")
        elif event_type == "response.audio.delta":
            # 收到音频数据（Base64）
            audio_data = response.get('delta')
    
    def on_close(self, code, msg):
        print(f"连接关闭: {msg}")

# 创建连接
conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=MyCallback(),
    url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
)

# 建立连接
conversation.connect()
```

#### 2. 会话配置事件

```python
import json

session_config = {
    "event_id": "event_001",  # 客户端生成的事件ID
    "type": "session.update",
    "session": {
        # 输出模态：["text"] 仅文本，["text", "audio"] 文本+音频
        "modalities": ["text", "audio"],
        
        # 输出语音角色
        "voice": "Cherry",  # 可选: Daisy, Alfie 等
        
        # 音频格式
        "input_audio_format": "pcm",
        "output_audio_format": "pcm",
        
        # 系统指令（可选）
        "instructions": "你是一个有帮助的 AI 助手",
        
        # 语音活动检测配置（可选）
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,  # 0-1，值越大越不敏感
            "silence_duration_ms": 800  # 静音多少ms后触发响应
        }
    }
}

# 发送配置
conversation.send_event(json.dumps(session_config))
```

#### 3. 发送文本输入

```python
import json
import time

# 添加文本
text_event = {
    "event_id": f"event_{int(time.time() * 1000)}",
    "type": "input_text_buffer.append",
    "text": "你好，请自我介绍"
}
conversation.send_event(json.dumps(text_event))

# 提交（触发模型响应）
commit_event = {
    "event_id": f"event_{int(time.time() * 1000)}",
    "type": "input_text_buffer.commit"
}
conversation.send_event(json.dumps(commit_event))
```

#### 4. 发送音频输入

```python
import base64

# 读取 PCM 音频文件
with open("audio.wav", "rb") as f:
    audio_data = f.read()

# Base64 编码
audio_base64 = base64.b64encode(audio_data).decode()

# 添加音频到缓冲区
audio_event = {
    "event_id": f"event_{int(time.time() * 1000)}",
    "type": "input_audio_buffer.append",
    "audio": audio_base64
}
conversation.send_event(json.dumps(audio_event))

# 提交（VAD 启用=自动，禁用=需要手动提交）
commit_event = {
    "event_id": f"event_{int(time.time() * 1000)}",
    "type": "input_audio_buffer.commit"
}
conversation.send_event(json.dumps(commit_event))
```

#### 5. 接收响应

```
响应事件类型：

文本响应：
├── response.audio_transcript.delta     # 流式文本片段
└── response.audio_transcript.done      # 完整文本

音频响应：
├── response.audio.delta                # 流式音频片段（Base64）
└── response.audio.done                 # 音频生成完成

错误处理：
└── server.error                        # 服务器错误

会话事件：
├── session.created                     # 会话已创建
└── response.done                       # 响应完成
```

### REST API 方式（备选）

#### 文本输入获取语音输出

```python
payload = {
    "model": "qwen3.5-omni-plus",
    "messages": [{
        "role": "user",
        "content": "你好，请用语音回复"
    }],
    "parameters": {
        "audio": {
            "input": False,   # 不使用音频输入
            "output": True    # 启用音频输出
        }
    }
}
```

#### 语音输入获取语音输出

```python
payload = {
    "model": "qwen3.5-omni-plus",
    "messages": [{
        "role": "user",
        "content": [
            {
                "type": "audio",
                "audio": f"data:audio/wav;base64,{audio_base64}"
            }
        ]
    }],
    "parameters": {
        "audio": {
            "input": True,    # 启用音频输入
            "output": True    # 启用音频输出
        }
    }
}
```

## 🎵 支持的音频格式和语音角色

### 音频格式
- **PCM** (推荐): 原始 PCM 数据，最常用
- **WAV**: 含有 PCM 编码的 WAV 文件
- **MP3**, **M4A**, **AAC**: 压缩格式

### 输出语音角色（Voice）
- `Cherry` - 女性，温柔
- `Daisy` - 女性，活泼
- `Alfie` - 男性，正式
- 更多角色请查看官方文档

## 📊 API 响应格式

### WebSocket 事件示例

```json
{
  "event_id": "event_xxx",
  "type": "response.audio_transcript.delta",
  "delta": "你好"
}
```

```json
{
  "event_id": "event_xxx",
  "type": "response.audio.delta",
  "delta": "base64_encoded_audio_data"
}
```

### REST API 响应示例

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "qwen3.5-omni-plus",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": [
          {
            "type": "text",
            "text": "这是文本响应"
          },
          {
            "type": "audio",
            "audio": "data:audio/wav;base64,..."
          }
        ]
      },
      "finish_reason": "stop"
    }
  ]
}
```

## 🔧 自定义测试

### 使用 test_omni_audio.py 进行自定义测试

```python
import asyncio
from test_omni_audio import QwenOmniAudioTester

async def custom_test():
    tester = QwenOmniAudioTester()
    
    # 文本输入测试
    result = await tester.test_text_input("你好，请告诉我今天的天气")
    
    # 音频输入测试
    result = await tester.test_audio_input("path/to/audio.wav")
    
    # 组合测试
    result = await tester.test_audio_input(
        "path/to/audio.wav",
        question="请问这段音频里说了什么？"
    )

asyncio.run(custom_test())
```

## ⚠️ 常见问题

### Q: WebSocket 连接失败？

**A:** 检查以下几点：
1. DashScope SDK 版本 >= 1.23.9
   ```bash
   pip install --upgrade dashscope
   ```
2. API Key 正确设置在 `.env` 或环境变量
3. 网络连接正常，能访问 `wss://dashscope.aliyuncs.com`
4. 防火墙允许 WebSocket 连接（端口 443）

### Q: 403 权限错误？

**A:** 这通常说明：
1. 账户未开通 qwen3.5-omni-plus 模型
2. API Key 无效或过期
3. 账户配额已用完

**解决方案：**
- 登录 [DashScope 控制面板](https://dashscope.aliyuncs.com)
- 检查模型开通情况
- 生成新的 API Key
- 检查余额和配额

### Q: 音频数据如何处理？

**A:** WebSocket 方式下：
1. 发送音频前需要 Base64 编码
2. 接收的音频也是 Base64 编码
3. PCM 格式是标准的、最推荐的格式

### Q: 如何实时播放输出音频？

**A:** 示例代码：
```python
import pyaudio
import base64
import numpy as np

# 音频参数
SAMPLE_RATE = 24000  # pcm 采样率
CHUNK_SIZE = 2048

def play_audio_chunk(base64_audio):
    # 解码
    audio_bytes = base64.b64decode(base64_audio)
    
    # 转换为数组
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
    
    # 播放
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        output=True,
        frames_per_buffer=CHUNK_SIZE
    )
    stream.write(audio_array.tobytes())
    stream.close()
    p.terminate()
```

### Q: 如何录制输入音频？

**A:** 示例代码：
```python
import pyaudio
import wave

SAMPLE_RATE = 24000
RECORD_SECONDS = 5

def record_audio(filename):
    p = pyaudio.PyAudio()
    
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=2048
    )
    
    frames = []
    for _ in range(0, int(SAMPLE_RATE / 2048 * RECORD_SECONDS)):
        data = stream.read(2048)
        frames.append(data)
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b''.join(frames))

# 使用
record_audio("input_audio.wav")
```

### Q: 如何调整语音活动检测敏感度？

**A:** 在会话配置中调整 `turn_detection`：

```python
"turn_detection": {
    "type": "server_vad",
    "threshold": 0.3,           # 0-1，越小越敏感
    "silence_duration_ms": 600  # 更小值=更快响应
}
```

- `threshold` 越小，检测越敏感
- `silence_duration_ms` 越小，响应越快
- 在嘈杂环境中增加这些值

### Q: VAD 禁用（手动模式）怎么用？

**A:** 如果不想用 VAD，设置为 `null`：

```python
"turn_detection": null  # 禁用 VAD，手动提交
```

然后手动发送 commit 事件来触发响应。

## 💡 使用建议

### 开发推荐流程
1. **初始化阶段**: 运行 `test_omni_realtime_quick.py` 快速验证
2. **功能测试**: 使用 `test_omni_realtime.py` 的各个测试模式
3. **交互式开发**: 使用交互模式调试
4. **集成部署**: 基于脚本代码集成到应用中

### 性能优化建议
- 使用 WebSocket 方式而不是 REST API（实时性更好）
- 启用服务端 VAD 可以减少延迟
- Base64 编码和解码可能是性能瓶颈，考虑用二进制传输
- 缓冲接收到的音频片段，批量处理

### 生产环境建议
- 添加完整的错误处理和重试逻辑
- 实现连接重连机制
- 监控 WebSocket 心跳
- 记录详细日志用于调试
- 限制单个连接的时长
- 实现请求队列管理多个并发连接

## 📚 相关资源

### 官方文档
- [阿里云 DashScope 文档](https://dashscope.aliyuncs.com)
- [Qwen 模型文档](https://qwen.aliyun.com)
- [Omni-Plus 实时 API 文档](https://help.aliyun.com/zh)

### 项目中的脚本文件
```
d:\code\health\
├── test_omni_realtime.py           # ⭐ 完整实时语音交互
├── test_omni_realtime_quick.py     # ⭐ 快速连接测试
├── test_omni_audio.py              # REST API 完整功能
├── test_omni_quick.py              # REST API 快速测试
├── diagnose_qwen_api.py            # API 诊断工具
└── OMNI_AUDIO_GUIDE.md             # 本指南
```

## 🎯 快速导航

| 场景 | 推荐脚本 | 命令 |
|------|---------|------|
| 快速验证 | `test_omni_realtime_quick.py` | `python test_omni_realtime_quick.py` |
| 交互式对话 | `test_omni_realtime.py` | `python test_omni_realtime.py` 然后选择选项 3 |
| 文本→语音 | `test_omni_realtime.py` | `python test_omni_realtime.py` 然后选择选项 1 |
| 语音→语音 | `test_omni_realtime.py` | `python test_omni_realtime.py` 然后选择选项 2 |
| API 诊断 | `diagnose_qwen_api.py` | `python diagnose_qwen_api.py` |

## 📝 修订历史

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-04-01 | 2.0 | 添加 WebSocket 实时方式，推荐使用 DashScope SDK |
| 2026-04-01 | 1.0 | 初始版本，包含 REST API 方式 |

---

**创建于**: 2026-04-01  
**最后更新**: 2026-04-01  
**维护人**: AI Assistant  
**状态**: ✅ 活跃维护
