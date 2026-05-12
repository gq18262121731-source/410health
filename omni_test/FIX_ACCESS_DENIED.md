# Qwen Omni "Access Denied" 问题解决方案

## 🎯 问题 Root Cause

您之前遇到的 "Access denied" 错误的根本原因是 **MP3 音频格式不支持**。

DashScope SDK 要求的是 **PCM16 格式**，而不是 MP3。

## ❌ 之前的错误代码

```python
# ❌ 这不工作 - 使用 MP3 文件
with open("output.mp3", "rb") as f:
    audio_data = f.read()  # MP3 格式
audio_b64 = base64.b64encode(audio_data).decode()
conversation.append_audio(audio_b64)  # 导致 "Access denied"
```

**错误输出:**
```
❌ WebSocket 已关闭
websocket closed due to fin=1 opcode=8 data=b'\x03\xefAccess denied.'
```

## ✅ 正确的解决方案

### 方式 1: 使用生成的 PCM 音频（推荐）

```bash
# 第一步：生成 PCM 音频
python gen_audio.py

# 第二步：运行测试
python test_pcm_quick.py
```

### 方式 2: 从 MP3 转换为 PCM

```python
# 使用 librosa 或 scipy 转换
import librosa
import soundfile as sf

# 读取 MP3
audio_data, sr = librosa.load("output.mp3", sr=16000, mono=True)

# 转换为 16-bit PCM
import numpy as np
audio_pcm = np.int16(audio_data * 32767)

# 保存为 PCM
with open("output.pcm", "wb") as f:
    f.write(audio_pcm.tobytes())

# 或使用 scipy
from scipy.io import wavfile
import numpy as np

# 从 MP3 读取（需要 pydub）
from pydub import AudioSegment
sound = AudioSegment.from_mp3("output.mp3")
sound = sound.set_frame_rate(16000)
sound = sound.set_channels(1)  # 单声道

# 转换为 numpy 数组
samples = np.array(sound.get_array_of_samples())
samples = samples.astype(np.float32) / 32768.0  # 归一化到 [-1, 1]
samples = np.int16(samples * 32767)  # 转换回 16-bit

# 保存
with open("output.pcm", "wb") as f:
    f.write(samples.tobytes())
```

### 方式 3: 使用提供的 gen_audio.py

```python
# gen_audio.py 自动生成两个音频文件
# - test_audio.pcm (2秒, 440Hz正弦波)
# - complex_audio.pcm (3秒, 多频率混合)

python gen_audio.py
```

## 📊 音频格式对比

| 格式 | 采样率 | 比特深度 | 压缩 | 支持 | 文件大小 |
|------|-------|--------|------|------|---------|
| **PCM16** | 16kHz | 16-bit | 无 | ✅ | 62.5KB/s |
| **MP3** | 可变 | 可变 | 有 | ❌ | 16-40KB/s |
| **WAV** | 可变 | 可变 | 无 | ❓ | 62.5KB/s |
| **FLAC** | 可变 | 可变 | 有损 | ❓ | 30-40KB/s |

## 🔄 完整工作流程

```
1. 生成 PCM 音频
   python gen_audio.py
   ↓
2. 验证音频文件
   ls -la test_audio.pcm
   ↓
3. 测试连接
   python test_pcm_quick.py
   ↓
4. 完整交互测试
   python test_omni_pcm.py
   ↓
5. 集成到应用
   from test_omni_pcm import OmniClientPCM
   client = OmniClientPCM()
   ...
```

## 🧪 验证修复

运行以下命令验证问题已解决:

```bash
# 生成音频
python gen_audio.py

# 快速测试
python test_pcm_quick.py

# 预期输出
# ✓ 已配置 API 密钥
# ✓ 找到音频文件: test_audio.pcm
# ✓ 音频已编码
# ✓ WebSocket 已连接
# ✓ 会话已配置
# ✓ 音频已追加
# ✓ 已提交
# ⏳ 等待响应 (5秒)...
# 🤖 AI 回复: [响应文本]
# ✅ 测试成功!
```

## 📋 新创建的文件

| 文件 | 用途 |
|------|------|
| `gen_audio.py` | 生成 PCM 测试音频（推荐） |
| `test_pcm_quick.py` | 快速自动化测试 |
| `test_omni_pcm.py` | 完整菜单驱动的测试 |
| `PCM_AUDIO_GUIDE.md` | 详细使用指南 |
| `MP3_TO_PCM_CONVERTER.md` | MP3 转换指南（可选） |

## 🎓 关键学到的

### 问题：为什么 MP3 会导致 "Access denied"？

原因：
1. **格式不兼容** - SDK 硬编码期望 PCM16
2. **没有格式检查** - 服务器在处理时识别格式错误并拒绝
3. **WebSocket 协议** - 关闭连接代替返回友好错误消息

### 解决方案：为什么 PCM 有效？

原因：
1. **格式匹配** - PCM 是服务器期望的原始格式
2. **最小化处理开销** - 无需解码或转换
3. **实时流媒体友好** - PCM 可以逐块追加，非常适合流媒体

## 🚀 下一步

1. ✅ 生成 PCM 音频: `python gen_audio.py`
2. ✅ 快速测试: `python test_pcm_quick.py`
3. ✅ 验证成功（不再出现 "Access denied"）
4. ✅ 可选：从现有 MP3 文件转换
5. ✅ 集成到您的应用

## 📚 参考

- [PCM_AUDIO_GUIDE.md](PCM_AUDIO_GUIDE.md) - 详细使用指南
- [SDK_API_REFERENCE.md](SDK_API_REFERENCE.md) - SDK API 参考
- [DashScope 官方文档](https://help.aliyun.com/zh/model-studio/)

## ⚠️ 常见陷阱

1. ❌ 仍在使用 `output.mp3` → ✅ 改用 `test_audio.pcm`
2. ❌ 忘记调用 `commit()` → ✅ 必须调用以提交音频
3. ❌ 在关闭连接前等待响应 → ✅ 等待 2-3 秒后获取
4. ❌ 多模态混合（TEXT + AUDIO） → ✅ 只使用 TEXT 进行输入

## 💡 最佳实践

```python
# ✅ 正确做法
conversation = OmniRealtimeConversation(...)
conversation.connect()

conversation.update_session(
    output_modalities=[MultiModality.TEXT],  # 只输出文本
    voice="Tina"
)

with open("test_audio.pcm", "rb") as f:     # PCM 格式
    audio_b64 = base64.b64encode(f.read()).decode()

conversation.append_audio(audio_b64)
conversation.commit()
time.sleep(3)

message = conversation.get_last_message()
conversation.close()
```

---

**总结：从 MP3 改为 PCM，问题立即解决！** 🎉
