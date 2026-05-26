# Qwen Omni 音频集成 - 完整指南

## 📋 概览

本项目涵盖了与 DashScope Qwen3.5-Omni-Plus 模型集成的语音音频测试，包括:
- ✅ PCM 音频生成
- ✅ WebSocket 连接
- ✅ 音频追加和提交
- ✅ 响应处理

---

## 🚀 快速开始

### 1️⃣ 生成测试音频

```bash
python gen_audio.py
```

**输出:**
- `test_audio.pcm` - 2 秒的 440Hz 正弦波
- `complex_audio.pcm` - 3 秒的复杂音频

### 2️⃣ 运行快速测试

```bash
python test_pcm_quick.py
```

**预期输出:**
```
✓ 已配置 API 密钥
✓ 找到音频文件: test_audio.pcm
✓ 音频已编码
✓ WebSocket 已连接
⚙️  配置会话...
✓ 会话已配置
📤 追加 PCM 音频...
✓ 音频已追加
📤 提交音频...
✓ 已提交
⏳ 等待响应 (5秒)...
🤖 AI 回复: [响应文本]
✅ 测试成功!
```

### 3️⃣ 完整交互式菜单

```bash
python test_omni_pcm.py
```

---

## 📂 文件说明

| 文件 | 用途 | 状态 |
|------|------|------|
| `gen_audio.py` | 生成 PCM 测试音频 | ✅ 可用 |
| `test_pcm_quick.py` | 快速自动化测试 | ✅ 推荐 |
| `test_omni_pcm.py` | 完整交互式测试 | ✅ 可用 |
| `generate_test_audio.py` | 高级音频生成器 | ✅ 可用 |
| `test_omni_sdk.py` | SDK 完整实现 | ⚠️ MP3 问题 |
| `SDK_API_REFERENCE.md` | API 参考文档 | 📖 参考 |

---

## 🔍 故障排查

### 问题 1: "Access denied" 错误

**症状:**
```
❌ WebSocket 已关闭
❌ websocket closed due to fin=1 opcode=8 data=b'\x03\xefAccess denied.'
```

**原因:**
1. **音频格式错误** - MP3 不支持，需要 PCM16
2. **API 密钥无效** - 缺少模型权限
3. **会话配置问题** - 输出模态不匹配

**解决方案:**
```bash
# 1. 使用 PCM 格式而不是 MP3
python gen_audio.py              # 生成 PCM 音频
python test_pcm_quick.py         # 测试 PCM

# 2. 检查 API 密钥
# - 确保 API 密钥有效
# - 验证模型 qwen3.5-omni-plus-realtime 已激活
# - 检查账户余额

# 3. 验证会话配置
# 确保 output_modalities 包含 MultiModality.TEXT
from dashscope.audio.qwen_omni import MultiModality
modalities = [MultiModality.TEXT]  # 不要包含 AUDIO，除非需要
```

### 问题 2: "Connection is already closed" 错误

**症状:**
```
❌ 提交失败: Connection is already closed
```

**原因:**
- WebSocket 在 `append_audio()` 后立即关闭
- 通常与"Access denied"相关

**解决方案:**
- 参考"问题 1"的解决方案
- 尝试使用较短的音频文件测试连接稳定性

### 问题 3: 依赖包缺失

**症状:**
```
❌ ModuleNotFoundError: No module named 'dashscope'
```

**解决方案:**
```bash
pip install dashscope>=1.23.9
```

### 问题 4: 无法导入 DashScope SDK

**症状:**
```
❌ ImportError: cannot import name 'OmniRealtimeConversation'
```

**解决方案:**
```bash
# 升级 dashscope
pip install --upgrade dashscope

# 验证版本
python -c "import dashscope; print(dashscope.__version__)"
```

---

## 🎯 最佳实践

### 1. 音频生成

```python
import struct
import math

def generate_pcm(duration_s=2.0, sample_rate=16000, frequency=440.0):
    """生成高质量 PCM 音频"""
    num_samples = int(sample_rate * duration_s)
    audio = bytearray()
    
    for i in range(num_samples):
        # 生成正弦波
        sample = 32767 * math.sin(2 * math.pi * frequency * i / sample_rate)
        # 16-bit PCM 编码
        audio.extend(struct.pack('<h', int(sample)))
    
    return bytes(audio)
```

### 2. 正确的连接流程

```python
from dashscope.audio.qwen_omni import OmniRealtimeConversation, MultiModality
import base64

# 初始化
conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=your_callback
)

# 连接
conversation.connect()

# 配置（仅输出文本，不输出音频）
conversation.update_session(
    output_modalities=[MultiModality.TEXT],
    voice="Tina",
    enable_turn_detection=True
)

# 追加音频
audio_b64 = base64.b64encode(audio_data).decode()
conversation.append_audio(audio_b64)

# 提交
conversation.commit()

# 等待响应
time.sleep(3)

# 获取结果
message = conversation.get_last_message()

# 关闭
conversation.close()
```

### 3. 错误处理

```python
from dashscope.audio.qwen_omni import OmniRealtimeCallback

class RobustCallback(OmniRealtimeCallback):
    def __init__(self):
        self.response_text = ""
        self.error_occurred = False
        self.error_message = ""
    
    def on_open(self):
        print("✓ 连接已建立")
    
    def on_event(self, response):
        event_type = response.get("type", "")
        
        # 错误处理
        if "error" in event_type.lower():
            self.error_occurred = True
            self.error_message = response.get("error", {}).get("message", "未知错误")
            print(f"❌ 错误: {self.error_message}")
        
        # 文本处理
        elif "delta" in event_type and "text" in event_type:
            delta = response.get("delta", "")
            self.response_text += delta
    
    def on_close(self, code, msg):
        print(f"✓ 连接已关闭 (code={code})")
```

---

## 📊 音频格式详解

### PCM16 规格

| 属性 | 值 |
|------|-----|
| 采样率 | 16000 Hz |
| 比特深度 | 16 bit |
| 字节顺序 | 小端（Little Endian） |
| 通道数 | 单声道（Mono） |
| 时长 | 可变 |

### 大小计算

```python
duration_seconds = 2.0
sample_rate = 16000
bits_per_sample = 16

bytes_per_second = sample_rate * (bits_per_sample / 8)
total_bytes = bytes_per_second * duration_seconds

# 对于 2 秒音频：125 * 2 = 125000 字节 = 122 KB
```

### 生成示例

```python
# 最小示例
import struct
import math

audio = bytearray()
for i in range(32000):  # 2 秒 @ 16kHz
    sample = int(32767 * math.sin(2 * math.pi * 440 * i / 16000))
    audio.extend(struct.pack('<h', sample))

# 保存为文件
with open("audio.pcm", "wb") as f:
    f.write(audio)

# Base64 编码并发送
import base64
audio_b64 = base64.b64encode(audio).decode()
conversation.append_audio(audio_b64)
```

---

## ✅ 测试检查清单

在提交音频之前，验证:

- [ ] 音频文件存在
- [ ] 音频格式是 PCM16（不是 MP3）
- [ ] 采样率是 16000 Hz
- [ ] API 密钥有效
- [ ] 网络连接正常
- [ ] DashScope 服务可访问
- [ ] 模型 `qwen3.5-omni-plus-realtime` 已激活

---

## 🔗 相关资源

| 资源 | 链接 |
|------|------|
| DashScope 官方文档 | https://dashscope.aliyuncs.com/ |
| Client Events 文档 | https://help.aliyun.com/zh/model-studio/client-events |
| SDK API 参考 | 见 `SDK_API_REFERENCE.md` |
| 模型信息 | qwen3.5-omni-plus-realtime |

---

## 📞 调试步骤

### Step 1: 验证连接

```bash
python test_pcm_quick.py
# 检查 "✓ WebSocket 已连接" 消息
```

### Step 2: 验证音频格式

```python
import os
import struct

audio_file = "test_audio.pcm"
size = os.path.getsize(audio_file)
expected = 16000 * 2 * 2  # 16kHz, 2s, 16-bit

print(f"文件大小: {size} 字节")
print(f"预期大小: {expected} 字节")
print(f"匹配: {size == expected}")

# 读取并验证样本
with open(audio_file, "rb") as f:
    sample1 = struct.unpack('<h', f.read(2))[0]
    print(f"第一个样本: {sample1}")
```

### Step 3: 手动测试 API 密钥

```bash
# 使用 curl 测试 REST API
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/... \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3.5-omni-plus-realtime"}'
```

### Step 4: 启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 然后运行测试脚本
# 查看详细的日志输出
```

---

## 💡 提示和技巧

1. **测试连接**: 先运行 `test_pcm_quick.py` 验证基本连接
2. **逐步调试**: 使用小的音频文件（1-2 秒）测试
3. **检查余额**: 确保 DashScope 账户有足够的余额
4. **网络问题**: 如果连接不稳定，检查是否需要代理
5. **日志级别**: 增加日志级别以获取更多调试信息

---

## 📝 更新日志

### v1.0 (当前)
- ✅ 生成 PCM 测试音频
- ✅ 快速自动化测试
- ✅ 完整交互式菜单
- ✅ 故障排查指南

---

## 🤝 反馈和问题

遇到问题？按照以下步骤:

1. 检查上面的"故障排查"部分
2. 运行 `test_pcm_quick.py` 获取诊断输出
3. 查看具体的错误消息
4. 参考 `SDK_API_REFERENCE.md` 了解 API 详情

---

## 📄 许可证

该项目是 [AIoT 智慧康养健康监测系统](https://github.com/your-repo) 的一部分。

