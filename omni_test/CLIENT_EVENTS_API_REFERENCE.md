# Qwen Omni 客户端事件官方 API 参考

> 基于官方文档: https://help.aliyun.com/zh/model-studio/client-events

## 📋 客户端事件概述

客户端通过发送 JSON 事件与 Omni 实时服务交互。所有事件都包含 `event_id` 和 `type` 字段。

## 🔑 核心客户端事件

### 1. session.update - 会话配置

**用途**: 建立 WebSocket 连接后首先发送，配置会话参数

**必选字段**:
- `event_id`: 客户端生成的唯一事件 ID
- `type`: 固定值 "session.update"

**session 对象参数**:

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `modalities` | array | 输出模态，可选值：`["text"]` 仅输出文本；`["text","audio"]` 输出文本与音频 | `["text","audio"]` |
| `voice` | string | 输出语音角色 | 见下表 |
| `input_audio_format` | string | 输入音频格式，支持: `pcm` | `pcm` |
| `output_audio_format` | string | 输出音频格式，支持: `pcm` | `pcm` |
| `instructions` | string | 系统提示词/角色设定 | - |
| `turn_detection` | object | VAD (语音活动检测) 配置 | 见下 |
| `temperature` | float | 采样温度 [0, 2) | 0.9 |
| `top_p` | float | 核采样阈值 (0, 1.0] | 1.0 |
| `top_k` | int | 采样候选集大小 | 50 |
| `max_tokens` | int | 最大输出 Token 数 | - |
| `presence_penalty` | float | 重复惩罚 [-2.0, 2.0] | 0.0 |
| `repetition_penalty` | float | 连续重复惩罚 (> 0) | 1.05 |
| `seed` | int | 随机数种子 [0, 2^31-1] | -1 |

**输出语音角色表**:

| 模型 | 默认语音 | 可选语音 |
|------|---------|---------|
| `qwen3.5-omni-plus-realtime` | Tina | Tina, Daisy, Alfie, Chelsie, 等 |
| `qwen3.5-omni-flash-realtime` | Cherry | Cherry, 等 |
| `qwen-omni-turbo-realtime` | Chelsie | Chelsie, 等 |

**VAD 配置** (`turn_detection` 对象):

```json
{
  "type": "server_vad",              // VAD 类型，固定值
  "threshold": 0.5,                   // 敏感度阈值 [0, 1]，越小越敏感
  "silence_duration_ms": 800          // 静音持续时间 (毫秒)
}
```

**示例**:

```json
{
  "event_id": "event_1234567890",
  "type": "session.update",
  "session": {
    "modalities": ["text", "audio"],
    "voice": "Tina",
    "input_audio_format": "pcm",
    "output_audio_format": "pcm",
    "instructions": "你是一个友好的旅游顾问，请用简洁的语言回答问题",
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "silence_duration_ms": 800
    },
    "temperature": 0.9,
    "max_tokens": 1024
  }
}
```

---

### 2. input_audio_buffer.append - 追加音频数据

**用途**: 向输入音频缓冲区添加音频数据

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | string | 事件 ID |
| `type` | string | 固定值 "input_audio_buffer.append" |
| `audio` | string | Base64 编码的音频数据 |

**示例**:

```json
{
  "event_id": "event_1234567891",
  "type": "input_audio_buffer.append",
  "audio": "UklGR..." // Base64 编码的 PCM 音频
}
```

---

### 3. input_audio_buffer.commit - 提交音频缓冲区

**用途**: 提交音频缓冲区，创建用户消息项

**说明**:
- **VAD 模式**: 服务端自动提交，客户端不需要发送
- **Manual 模式**: 客户端必须手动提交

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | string | 事件 ID |
| `type` | string | 固定值 "input_audio_buffer.commit" |

**示例**:

```json
{
  "event_id": "event_1234567892",
  "type": "input_audio_buffer.commit"
}
```

---

### 4. input_audio_buffer.clear - 清除音频缓冲区

**用途**: 清除缓冲区中的所有音频数据

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | string | 事件 ID |
| `type` | string | 固定值 "input_audio_buffer.clear" |

**示例**:

```json
{
  "event_id": "event_1234567893",
  "type": "input_audio_buffer.clear"
}
```

---

### 5. input_image_buffer.append - 追加图像数据

**用途**: 向图像缓冲区添加图像（可选，通常与音频配合）

**限制**:
- 格式: JPG 或 JPEG
- 分辨率: 480p-1080p（推荐 720p）
- 大小: 不超过 500KB (Base64 编码前)
- 频率: 建议 1 张/秒
- 前提: 必须先发送至少一次 `input_audio_buffer.append`

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | string | 事件 ID |
| `type` | string | 固定值 "input_image_buffer.append" |
| `image` | string | Base64 编码的图像数据 |

**示例**:

```json
{
  "event_id": "event_1234567894",
  "type": "input_image_buffer.append",
  "image": "xxx" // Base64 编码的 JPG 图像
}
```

---

### 6. response.create - 创建响应

**用途**: 指示服务端创建模型响应

**说明**: VAD 模式下服务端会自动创建，无需发送；Manual 模式下需要手动发送

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | string | 事件 ID |
| `type` | string | 固定值 "response.create" |

**示例**:

```json
{
  "event_id": "event_1234567895",
  "type": "response.create"
}
```

---

### 7. response.cancel - 取消响应

**用途**: 取消当前进行中的模型响应

**说明**: 如果没有响应可供取消，服务端返回错误事件

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | string | 事件 ID |
| `type` | string | 固定值 "response.cancel" |

**示例**:

```json
{
  "event_id": "event_1234567896",
  "type": "response.cancel"
}
```

---

## 🔄 典型交互流程

### 流程 1: 文本输入 → 文本输出

```
1. 客户端 → session.update (配置会话)
2. 服务端 → session.updated (确认配置)
3. 客户端 → 通过其他方式发送文本输入
4. 服务端 → response.text.delta (流式文本)
5. 服务端 → response.text.done (完成)
```

### 流程 2: 音频输入 → 音频输出 (VAD 模式)

```
1. 客户端 → session.update (modalities: ["text", "audio"])
2. 服务端 → session.updated
3. 客户端 → input_audio_buffer.append (追加音频块)
4. 客户端 → input_audio_buffer.append (继续追加)
5. [服务端自动检测到静音，自动 commit]
6. 服务端 → input_audio_buffer.committed
7. 服务端 → response.audio_transcript.delta (文本转录)
8. 服务端 → response.audio.delta (输出音频)
9. 服务端 → response.done (完成)
```

### 流程 3: 音频输入 → 音频输出 (Manual 模式)

```
1. 客户端 → session.update (turn_detection: null)
2. 服务端 → session.updated
3. 客户端 → input_audio_buffer.append (追加音频块)
4. 客户端 → input_audio_buffer.append (继续追加)
5. 客户端 → input_audio_buffer.commit (手动提交)
6. 服务端 → input_audio_buffer.committed
7. 服务端 → response.create (自动创建或由客户端触发)
8. 服务端 → response.audio_transcript.delta (文本转录)
9. 服务端 → response.audio.delta (输出音频)
10. 服务端 → response.done
```

---

## 📥 服务端响应事件参考

服务端返回的主要事件类型：

| 事件类型 | 说明 |
|---------|------|
| `session.created` | 会话已创建 |
| `session.updated` | 会话配置已更新 |
| `response.text.delta` | 文本响应片段 |
| `response.text.done` | 文本响应完成 |
| `response.audio_transcript.delta` | 音频转录片段 |
| `response.audio_transcript.done` | 音频转录完成 |
| `response.audio.delta` | 音频输出片段 (Base64) |
| `response.audio.done` | 音频生成完成 |
| `input_audio_buffer.committed` | 音频缓冲区已提交 |
| `input_audio_buffer.cleared` | 音频缓冲区已清除 |
| `response.done` | 响应完成 |
| `server.error` | 服务端错误 |

---

## 💻 Python 实现示例

### 生成事件 ID

```python
import uuid
import time

def generate_event_id():
    return f"event_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
```

### 准备 session.update 事件

```python
import json

session_update = {
    "event_id": generate_event_id(),
    "type": "session.update",
    "session": {
        "modalities": ["text", "audio"],
        "voice": "Tina",
        "input_audio_format": "pcm",
        "output_audio_format": "pcm",
        "instructions": "你是一个友好的助手",
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "silence_duration_ms": 800
        }
    }
}

# 发送事件
event_json = json.dumps(session_update)
# conversation.send(event_json)  # 具体方法取决于 SDK
```

### 准备音频追加事件

```python
import base64

# 读取 PCM 音频数据
with open("audio.pcm", "rb") as f:
    audio_bytes = f.read()

audio_base64 = base64.b64encode(audio_bytes).decode()

audio_append = {
    "event_id": generate_event_id(),
    "type": "input_audio_buffer.append",
    "audio": audio_base64
}

# 发送事件
event_json = json.dumps(audio_append)
# conversation.send(event_json)
```

### 处理服务端事件

```python
class EventHandler:
    def handle_event(self, event_dict):
        event_type = event_dict.get("type")
        
        if event_type == "response.text.delta":
            text = event_dict.get("delta", "")
            print(f"🤖 {text}", end="", flush=True)
        
        elif event_type == "response.text.done":
            print()
        
        elif event_type == "response.audio.delta":
            audio_b64 = event_dict.get("delta", "")
            # 处理音频数据
        
        elif event_type == "server.error":
            error = event_dict.get("error", {})
            print(f"❌ {error.get('message')}")
```

---

## 🎯 最佳实践

### 1. 事件 ID 生成
```python
# 确保每个事件都有唯一的 ID
event_id = f"event_{int(time.time() * 1000)}"
```

### 2. 会话配置顺序
```
1. 建立 WebSocket 连接
2. 立即发送 session.update
3. 等待 session.updated 响应
4. 然后发送其他事件
```

### 3. VAD 配置选择
- **启用 VAD** (推荐): 自动检测说话结束，降低延迟
- **禁用 VAD** (手动模式): 完全控制，适合特定场景

### 4. 音频处理
- 使用 PCM 格式（16kHz, 16-bit, mono）
- Base64 编码后再发送
- 及时提交缓冲区避免堆积

### 5. 错误处理
```python
if event_type == "server.error":
    error_code = event.get("error", {}).get("code")
    error_msg = event.get("error", {}).get("message")
    # 根据错误类型采取不同的处理策略
```

---

## 🔗 相关资源

- 官方文档: https://help.aliyun.com/zh/model-studio/client-events
- 服务端事件: https://help.aliyun.com/zh/model-studio/server-events
- 实时 API 指南: https://help.aliyun.com/zh/model-studio/realtime

---

**版本**: 1.0  
**更新时间**: 2026-04-01  
**来源**: 阿里云官方文档
