# Qwen Omni 快速参考卡

## 🎯 问题回顾

您遇到的 **"Access denied"** 错误是由于使用了 **MP3 格式**而不是 **PCM 格式**。

## ✅ 解决方案（3 步）

### 第 1 步：生成 PCM 音频

```bash
python gen_audio.py
```

**输出:**
- ✓ `test_audio.pcm` (62.5 KB, 2 秒)
- ✓ `complex_audio.pcm` (93.8 KB, 3 秒)

### 第 2 步：快速测试

```bash
python test_pcm_quick.py
```

**预期输出:**
```
✓ 已配置 API 密钥
✓ 找到音频文件: test_audio.pcm
✓ 音频已编码
✓ WebSocket 已连接
✓ 会话已配置
✓ 音频已追加
✓ 已提交
⏳ 等待响应 (5秒)...
🤖 AI 回复: <响应内容>
✅ 测试成功!
```

### 第 3 步：集成到应用

```python
from dashscope.audio.qwen_omni import OmniRealtimeConversation, MultiModality
import base64

# 连接
conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=your_callback
)
conversation.connect()

# 配置
conversation.update_session(
    output_modalities=[MultiModality.TEXT],  # 文本输出
    voice="Tina"                              # Tina, Daisy, Alfie, Chelsie
)

# 追加并提交 PCM 音频
with open("test_audio.pcm", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()

conversation.append_audio(audio_b64)
conversation.commit()

# 获取响应
import time
time.sleep(3)
message = conversation.get_last_message()

conversation.close()
```

## 🔧 新增工具

| 工具 | 用途 | 命令 |
|------|------|------|
| `gen_audio.py` | 生成 PCM 音频 | `python gen_audio.py` |
| `test_pcm_quick.py` | 快速自动化测试 | `python test_pcm_quick.py` |
| `test_omni_pcm.py` | 交互式完整测试 | `python test_omni_pcm.py` |
| `mp3_to_pcm.py` | MP3 转 PCM 转换 | `python mp3_to_pcm.py input.mp3` |
| `diagnose_omni.py` | 系统诊断工具 | `python diagnose_omni.py` |

## 📂 新增文档

| 文档 | 内容 |
|------|------|
| `PCM_AUDIO_GUIDE.md` | 详细使用指南 |
| `FIX_ACCESS_DENIED.md` | 问题原因和解决方案 |
| 此文件 | 快速参考卡 |

## 🚀 一键运行

```bash
# 第一次运行（完整设置）
python gen_audio.py \
  && python diagnose_omni.py \
  && python test_pcm_quick.py

# 后续运行（快速测试）
python test_pcm_quick.py
```

## 🎵 音频格式对比

| 格式 | 支持 | 原因 |
|------|------|------|
| PCM16 16kHz | ✅ | SDK 原生支持 |
| MP3 | ❌ | 需要解码，格式不兼容 |
| WAV | ❓ | 未验证 |
| FLAC | ❓ | 未验证 |

## 🚨 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `Access denied` | MP3 格式 | 使用 PCM 格式 |
| `Connection is already closed` | 连接被拒绝 | 检查 API 密钥 |
| `ModuleNotFoundError: dashscope` | 缺少库 | `pip install dashscope` |
| 无响应 | 等待时间不足 | 增加到 3-5 秒 |

## 💡 技巧

1. **先验证连接** - 运行 `diagnose_omni.py` 检查系统
2. **使用预生成音频** - `test_audio.pcm` 是 2 秒的简单音频
3. **检查 API 密钥** - 确保有音频权限和账户余额
4. **逐步调试** - 先测试文本，再测试音频

## 🔗 API 速查

### 初始化
```python
conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=callback
)
```

### 主要方法
```python
conversation.connect()                           # 连接
conversation.update_session(                     # 配置
    output_modalities=[MultiModality.TEXT],
    voice="Tina"
)
conversation.append_audio(audio_b64)            # 追加音频
conversation.commit()                           # 提交
message = conversation.get_last_message()       # 获取响应
conversation.close()                            # 关闭
```

### 回调事件
```python
class MyCallback(OmniRealtimeCallback):
    def on_open(self):                          # 连接打开
        pass
    
    def on_event(self, response):               # 收到事件
        if "error" in response.get("type", ""):
            print(f"Error: {response}")
        elif "delta" in response.get("type", ""):
            print(response.get("delta", ""), end="")
    
    def on_close(self, code, msg):             # 连接关闭
        pass
```

### 语音角色
```python
# 可用的语音角色
voice_options = ["Tina", "Daisy", "Alfie", "Chelsie"]

# 使用示例
conversation.update_session(voice="Daisy")
```

## 📊 文件大小参考

| 时长 | 字节数 | KB |
|------|--------|-----|
| 1 秒 | 32,000 | 31 |
| 2 秒 | 64,000 | 62 |
| 3 秒 | 96,000 | 94 |
| 5 秒 | 160,000 | 156 |
| 10 秒 | 320,000 | 312 |

## ✔️ 测试检查清单

在运行应用前检查:

- [ ] `test_audio.pcm` 存在 (或已生成)
- [ ] `python diagnose_omni.py` 通过
- [ ] `python test_pcm_quick.py` 成功
- [ ] API 密钥已设置环境变量或代码中
- [ ] 网络连接正常
- [ ] DashScope 账户有余额

## 🔄 从 MP3 迁移

如果您有现有的 MP3 文件:

```bash
# 安装转换工具
pip install librosa

# 转换 MP3 到 PCM
python mp3_to_pcm.py your_audio.mp3 -o your_audio.pcm --verify

# 在代码中使用
with open("your_audio.pcm", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()
conversation.append_audio(audio_b64)
```

## 🎓 核心知识点

### 为什么 PCM 有效？
- **原生格式** - SDK 直接支持，无需解码
- **效率高** - 解析快，适合实时流媒体
- **兼容性好** - 标准化的 16-bit 采样

### 为什么 MP3 不行？
- **编码格式** - 需要 MP3 解码器（SDK 没有）
- **不支持流媒体** - MP3 需要完整文件头
- **服务器拒绝** - 格式不兼容导致 "Access denied"

## 📞 获取帮助

1. 运行诊断工具: `python diagnose_omni.py`
2. 查看完整指南: [PCM_AUDIO_GUIDE.md](PCM_AUDIO_GUIDE.md)
3. 了解问题根源: [FIX_ACCESS_DENIED.md](FIX_ACCESS_DENIED.md)
4. 查看 SDK 参考: [SDK_API_REFERENCE.md](SDK_API_REFERENCE.md)

---

**总结：从 MP3 改用 PCM，问题解决！** ✅
