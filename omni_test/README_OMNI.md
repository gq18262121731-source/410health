# Qwen3.5-Omni-Plus 实时语音交互 - 脚本总结

## 📁 文件清单

### 核心脚本

| 文件 | 用途 | 依赖 | 推荐使用场景 |
|------|------|------|-----------|
| **test_omni_realtime_quick.py** | ⭐ 快速连接测试 | dashscope | 第一步验证连接 |
| **test_omni_realtime.py** | ⭐ 完整实时语音交互 | dashscope | 主要开发工具 |
| **omni_integration_examples.py** | 集成示例库 | dashscope | 学习集成方法 |
| **test_omni_audio.py** | REST API 完整功能 | requests, httpx | 备选方案 |
| **test_omni_quick.py** | REST API 快速测试 | requests | 备选方案 |
| **diagnose_qwen_api.py** | API 诊断工具 | requests | 故障排除 |

### 文档

| 文件 | 内容 | 推荐阅读 |
|------|------|---------|
| **QUICKSTART.md** | 快速开始指南 | 👈 首先阅读 |
| **OMNI_AUDIO_GUIDE.md** | 完整功能文档 | 需要详细信息时 |
| **README_OMNI.txt** | 本文件 | 概览和导航 |

## 🚀 使用流程

### 第 1 步：验证安装
```bash
python test_omni_realtime_quick.py
```
✅ 通过后进入第 2 步

### 第 2 步：尝试交互
```bash
python test_omni_realtime.py
# 选择: 1 (文本→语音) 或 3 (交互模式)
```

### 第 3 步：学习集成
```bash
python omni_integration_examples.py
# 查看 5 个实用集成示例
```

### 第 4 步：开发应用
基于示例代码开发自己的应用

## 📚 快速参考

### 最简单的代码示例

```python
from omni_integration_examples import SimpleAudioTester

# 创建测试器
tester = SimpleAudioTester(voice="Cherry")

# 启动
tester.start()

# 问问题
response = tester.ask("你好！")
print(response)

# 关闭
tester.close()
```

### 完整的类使用

```python
from test_omni_realtime import QwenOmniRealtimeClient

# 创建客户端
client = QwenOmniRealtimeClient(voice="Cherry")

# 连接
if client.connect():
    # 配置会话
    client.configure_session(
        instructions="你是一个旅游顾问",
        modalities=["text", "audio"]
    )
    
    # 发送文本
    import time
    time.sleep(1)
    client.send_text_input("推荐一个好玩的地方")
    
    # 等待响应
    time.sleep(3)
    
    # 保存音频
    client.save_output_audio("response.wav")
    
    # 关闭连接
    client.close()
```

## 🎯 按需求选择脚本

### 我只想快速测试一下...
→ **test_omni_realtime_quick.py**

### 我想用文本输入获得语音输出...
→ **test_omni_realtime.py** (选项 1)

### 我想进行实时对话...
→ **test_omni_realtime.py** (选项 3)

### 我想学习如何集成...
→ **omni_integration_examples.py**

### 我的模型有权限问题...
→ **diagnose_qwen_api.py**

### 我想用旧的 REST API...
→ **test_omni_audio.py**

## 🔑 关键特性

### WebSocket 实时方式（推荐）
- ✅ 低延迟实时交互
- ✅ 支持双向语音
- ✅ 官方 SDK 支持
- ✅ 稳定可靠

### REST API 方式（备选）
- ✅ 简单直接
- ✅ 支持一次性请求
- ✅ 易于集成
- ⚠️ 当前有权限问题

## 💡 常用操作

### 修改输出语音

```python
client = QwenOmniRealtimeClient(voice="Daisy")  # 可选值: Cherry, Daisy, Alfie
```

### 修改会话指令

```python
client.configure_session(
    instructions="你是一个在线教师，请用简明扼要的语言解释概念"
)
```

### 启用/禁用 VAD

启用 (默认):
```python
"turn_detection": {
    "type": "server_vad",
    "threshold": 0.5,
    "silence_duration_ms": 800
}
```

禁用 (手动提交):
```python
"turn_detection": null
```

## 📊 API 对比

| 特性 | WebSocket | REST API |
|------|-----------|----------|
| 实时性 | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 延迟 | 极低 | 较高 |
| 双向交互 | ✅ | ⚠️ |
| 流式接收 | ✅ | ❌ |
| 稳定性 | ✅ | ⚠️ |
| 代码复杂度 | 中等 | 简单 |

## 🛠️ 安装命令速查

```bash
# 基础安装
pip install dashscope

# 升级
pip install --upgrade dashscope

# 验证版本
python -c "import dashscope; print(dashscope.__version__)"

# 如需 REST API
pip install requests

# 如需 REST API 异步
pip install httpx

# 如需音频处理
pip install pyaudio soundfile numpy
```

## ⚙️ 环境变量配置

在 `.env` 文件中设置:

```env
# 必需
DASHSCOPE_API_KEY=sk-xxxxxxxxx
# 或
QWEN_API_KEY=sk-xxxxxxxxx

# 可选，脚本会自动检测
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_OMNI_MODEL=qwen3.5-omni-plus
```

## 📞 故障排除速查

| 问题 | 解决 |
|------|------|
| `ImportError: dashscope` | `pip install dashscope` |
| 连接超时 | 检查网络和防火墙 |
| 403 权限错误 | 检查 API Key 和账户配额 |
| 无响应 | 尝试增加等待时间 |
| 音频质量差 | 检查输入音频和语言设置 |

## 📖 文档导航

- **快速开始** → [QUICKSTART.md](QUICKSTART.md)
- **完整文档** → [OMNI_AUDIO_GUIDE.md](OMNI_AUDIO_GUIDE.md)
- **DashScope 官方** → https://dashscope.aliyuncs.com
- **Qwen 中心** → https://qwen.aliyun.com

## 🎓 学习顺序

1. 📖 阅读 [QUICKSTART.md](QUICKSTART.md)
2. 🚀 运行 `test_omni_realtime_quick.py`
3. 💬 运行 `test_omni_realtime.py` (交互模式)
4. 📚 查看 `omni_integration_examples.py` 的示例
5. 💻 基于示例开发自己的应用

## 🎯 典型集成场景

### 场景 1: 聊天机器人
```python
# 使用 SimpleAudioTester 处理用户输入
# 保存音频响应供播放
```

### 场景 2: 客服系统
```python
# 使用 QwenOmniRealtimeClient 处理来电
# 启用 VAD 自动检测说话结束
```

### 场景 3: 教育应用
```python
# 自定义 instructions 作为教师角色
# 多轮对话保持上下文
```

### 场景 4: 健康助手
```python
# 基于用户数据生成提示
# 使用 Daisy 语音营造温暖氛围
```

## ✨ 高级技巧

### 技巧 1: 保存完整对话
```python
# 在 on_event 中记录所有响应
class LoggingCallback(OmniRealtimeCallback):
    def on_event(self, response):
        with open("conversation.log", "a") as f:
            f.write(json.dumps(response) + "\n")
```

### 技巧 2: 实时音频播放
```python
# 在 on_event 中流式解码和播放
# 需要 pyaudio 库支持
```

### 技巧 3: 超时控制
```python
# 实现定时器
# 超过时间限制时手动 commit
```

## 📋 检查清单

开始前请确保:

- [ ] 已安装 dashscope (>= 1.23.9)
- [ ] .env 中有有效的 API Key
- [ ] 网络连接正常
- [ ] 账户有足够配额
- [ ] 模型已在控制面板开通

## 🚀 马上开始

```bash
# 一行命令快速测试
python test_omni_realtime_quick.py
```

如果成功，恭喜！开发愉快！

---

**版本**: 2.0  
**更新时间**: 2026-04-01  
**状态**: ✅ 活跃维护
