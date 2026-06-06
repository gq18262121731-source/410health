# DashScope SDK OmniRealtimeConversation API 参考

> 基于 dashscope >= 1.23.9 的实际 API 检查

## 🎯 核心方法

### 1. connect()
**建立 WebSocket 连接**

```python
conversation.connect()
```

### 2. update_session(output_modalities, voice=None, ...)
**配置会话参数**

```python
conversation.update_session(
    output_modalities=[MultiModality.TEXT, MultiModality.AUDIO],
    voice="Tina",
    enable_turn_detection=True,
    turn_detection_type="server_vad",
    turn_detection_threshold=0.2,
    turn_detection_silence_duration_ms=800
)
```

**参数说明**:
- `output_modalities`: 输出模态，使用 `MultiModality.TEXT` 和/或 `MultiModality.AUDIO`
- `voice`: 输出语音角色（Tina, Daisy, Alfie, 等）
- `enable_input_audio_transcription`: 是否启用音频转录（默认 True）
- `enable_turn_detection`: 是否启用 VAD（默认 True）
- `turn_detection_type`: VAD 类型（默认 "server_vad"）
- `turn_detection_threshold`: VAD 敏感度（默认 0.2）
- `turn_detection_silence_duration_ms`: 静音时限（默认 800ms）

### 3. append_audio(audio_b64)
**追加 Base64 编码的音频数据**

```python
import base64

with open("audio.pcm", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()

conversation.append_audio(audio_b64)
```

### 4. append_video(video_b64)
**追加 Base64 编码的视频/图像数据**

```python
with open("image.jpg", "rb") as f:
    video_b64 = base64.b64encode(f.read()).decode()

conversation.append_video(video_b64)
```

### 5. commit()
**提交音频/视频缓冲区**

```python
conversation.commit()
```

### 6. create_response(instructions=None, output_modalities=None)
**创建响应（Manual 模式下需要）**

```python
conversation.create_response(
    instructions="你是一个天气预报员",
    output_modalities=[MultiModality.TEXT, MultiModality.AUDIO]
)
```

### 7. cancel_response()
**取消当前响应**

```python
conversation.cancel_response()
```

### 8. clear_appended_audio()
**清除已追加的音频缓冲**

```python
conversation.clear_appended_audio()
```

### 9. get_last_message()
**获取最后的 AI 消息**

```python
message = conversation.get_last_message()
print(f"AI 说: {message}")
```

**返回值**: 字符串，AI 的最后一条消息

### 10. get_last_response_id()
**获取最后的响应 ID**

```python
response_id = conversation.get_last_response_id()
```

### 11. get_session_id()
**获取会话 ID**

```python
session_id = conversation.get_session_id()
```

### 12. get_last_first_text_delay()
**获取最后一条消息的首字延迟**

```python
delay_ms = conversation.get_last_first_text_delay()
print(f"首字延迟: {delay_ms}ms")
```

### 13. get_last_first_audio_delay()
**获取音频的首字延迟**

```python
delay_ms = conversation.get_last_first_audio_delay()
```

### 14. end_session(timeout=20)
**结束会话（同步）**

```python
conversation.end_session(timeout=20)
```

### 15. end_session_async()
**异步结束会话**

```python
conversation.end_session_async()
```

### 16. close()
**关闭连接**

```python
conversation.close()
```

### 17. send_raw(raw_data)
**发送原始数据（JSON 字符串）**

```python
import json

event = {
    "type": "session.update",
    "session": {...}
}
conversation.send_raw(json.dumps(event))
```

## 🔔 回调方法

继承 `OmniRealtimeCallback` 并实现：

```python
class MyCallback(OmniRealtimeCallback):
    def on_open(self) -> None:
        """连接已建立"""
        print("连接成功")
    
    def on_event(self, response: dict) -> None:
        """接收事件"""
        event_type = response.get("type")
        print(f"事件: {event_type}")
    
    def on_close(self, close_status_code: int, close_msg: str) -> None:
        """连接已关闭"""
        print(f"连接关闭: {close_msg}")
```

## 📋 MultiModality 枚举值

```python
from dashscope.audio.qwen_omni import MultiModality

MultiModality.TEXT       # 文本
MultiModality.AUDIO      # 音频
```

## 🎤 支持的语音角色

| 模型 | 默认语音 | 其他选项 |
|------|--------|--------|
| qwen3.5-omni-plus-realtime | Tina | Daisy, Alfie, Chelsie |
| qwen3.5-omni-flash-realtime | Cherry | ... |
| qwen-omni-turbo-realtime | Chelsie | ... |

## 📊 典型使用流程

### 文本输入 → 文本输出

```python
from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality

class MyCallback(OmniRealtimeCallback):
    def on_event(self, response):
        if response.get("type") == "response.text.delta":
            print(response.get("delta"), end="", flush=True)

callback = MyCallback()
conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=callback
)

conversation.connect()
conversation.update_session(
    output_modalities=[MultiModality.TEXT],
    voice="Tina"
)

# 等待后获取消息
import time
time.sleep(2)
message = conversation.get_last_message()
print(f"\nAI: {message}")

conversation.close()
```

### 音频输入 → 音频输出

```python
import base64

conversation.connect()
conversation.update_session(
    output_modalities=[MultiModality.TEXT, MultiModality.AUDIO],
    voice="Tina",
    enable_turn_detection=True
)

# 读取音频
with open("input.pcm", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()

# 追加并提交
conversation.append_audio(audio_b64)
conversation.commit()

# 等待响应
time.sleep(3)
message = conversation.get_last_message()
print(f"转录: {message}")

conversation.close()
```

## ⚙️ 初始化参数

```python
OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",  # 模型名称
    callback=callback,                    # 回调处理器
    headers=None,                         # 自定义 HTTP 头
    workspace=None,                       # 工作空间 ID
    url=None,                             # WebSocket URL（默认自动）
    api_key=None,                         # API Key（从环境变量读取）
    additional_params=None                # 额外参数
)
```

## 🔍 实际 API 对比

| 我最初的设计 | 实际 SDK API | 说明 |
|-----------|-----------|------|
| `send_event()` | `send_raw()` / `update_session()` / `append_audio()` 等 | SDK 提供高级方法 |
| session.update 事件 | `update_session()` 方法 | 已封装为方法 |
| input_audio_buffer.append 事件 | `append_audio()` 方法 | 已封装为方法 |
| input_audio_buffer.commit 事件 | `commit()` 方法 | 已封装为方法 |
| 手动事件循环 | 自动触发回调 | SDK 自动处理 |

## 💡 重要提示

1. **事件处理**: 不需要手动发送低级事件，SDK 已高度封装
2. **消息获取**: 使用 `get_last_message()` 获取回复
3. **回调处理**: 通过 `on_event()` 接收实时数据流
4. **自动管理**: SDK 自动管理连接、缓冲和事件序列
5. **错误处理**: 建议使用 try-except 包装所有调用

## 🚀 完整示例

```python
from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
import os
from dotenv import load_dotenv

load_dotenv()

class MyCallback(OmniRealtimeCallback):
    def on_open(self):
        print("✅ 连接成功")
    
    def on_event(self, response):
        if "text" in response.get("type", ""):
            delta = response.get("delta", "")
            if "delta" in response.get("type", ""):
                print(delta, end="", flush=True)
    
    def on_close(self, code, msg):
        print(f"\n✓ 连接关闭")

conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=MyCallback(),
    api_key=os.getenv("DASHSCOPE_API_KEY")
)

try:
    conversation.connect()
    
    conversation.update_session(
        output_modalities=[MultiModality.TEXT, MultiModality.AUDIO],
        voice="Tina"
    )
    
    # 等待响应
    import time
    time.sleep(2)
    
    # 获取消息
    message = conversation.get_last_message()
    print(f"\nAI: {message}")

finally:
    conversation.end_session()
    conversation.close()
```

---

**版本**: 1.23.9+  
**来源**: SDK 自省和诊断  
**最后更新**: 2026-04-01
