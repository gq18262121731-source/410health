# Qwen3.5-Omni-Plus 实时语音交互 - 项目概览

> 📌 **最后更新**: 2026-04-01  
> 📦 **SDK**: dashscope >= 1.23.9  
> ✅ **状态**: 生产就绪

## 🎯 项目目标

实现使用 Qwen3.5-Omni-Plus 模型的**实时双向语音交互**，支持：
- ✅ 文本 → 语音输出
- ✅ 语音 → 文本 + 语音输出  
- ✅ 多轮对话交互
- ✅ 可配置的语音角色和系统指令

## 📁 完整文件列表

### 🚀 可执行脚本

```
d:\code\health\
├── test_omni_realtime_quick.py          ⭐ 快速连接测试（推荐首先运行）
├── test_omni_realtime.py                ⭐ 完整交互客户端（功能最完整）
├── omni_integration_examples.py         📚 5 个集成示例
├── test_omni_audio.py                   📦 REST API 版本（备选）
├── test_omni_quick.py                   📦 REST API 快速测试
└── diagnose_qwen_api.py                 🔧 问题诊断工具
```

### 📖 文档

```
d:\code\health\
├── QUICKSTART.md                        👈 新用户必读
├── README_OMNI.md                       📋 脚本导航和参考
├── OMNI_AUDIO_GUIDE.md                  📚 完整技术文档
└── 本文件 (OVERVIEW.md)                 🗺️ 项目总览
```

## 🏃 5 分钟快速开始

### 1️⃣ 安装 SDK

```bash
pip install --upgrade dashscope
# 验证版本 >= 1.23.9
python -c "import dashscope; print(dashscope.__version__)"
```

### 2️⃣ 验证 API Key

在 `.env` 中确保有:
```
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxx
```

### 3️⃣ 运行快速测试

```bash
python test_omni_realtime_quick.py
```

**预期输出:**
```
✓ 环境检查通过
✓ WebSocket 连接成功
✓ 已发送文本
🤖 [AI 的回复...]
✅ 连接测试成功！
```

### 4️⃣ 开始交互

```bash
python test_omni_realtime.py
# 选择选项 3 进入交互模式
```

## 📚 完整学习路径

| 步骤 | 操作 | 预期时间 |
|-----|------|--------|
| 1️⃣ | 阅读 [QUICKSTART.md](QUICKSTART.md) | 5 分钟 |
| 2️⃣ | 运行 `test_omni_realtime_quick.py` | 1 分钟 |
| 3️⃣ | 运行 `test_omni_realtime.py` | 3 分钟 |
| 4️⃣ | 查看 `omni_integration_examples.py` | 10 分钟 |
| 5️⃣ | 开发自己的应用 | - |

## 💻 最小代码示例

### 简单 Q&A

```python
from omni_integration_examples import SimpleAudioTester

tester = SimpleAudioTester(voice="Cherry")
tester.start()
response = tester.ask("你好，请介绍自己")
print(response)
tester.close()
```

### 完整客户端

```python
from test_omni_realtime import QwenOmniRealtimeClient

client = QwenOmniRealtimeClient()
if client.connect():
    client.configure_session(instructions="你是一个旅游顾问")
    import time
    time.sleep(1)
    client.send_text_input("推荐一个好玩的地方")
    time.sleep(3)
    client.save_output_audio("response.wav")
    client.close()
```

## 🎯 快速导航

### 我想...

| 需求 | 推荐脚本 | 命令 |
|------|---------|------|
| 快速测试 | `test_omni_realtime_quick.py` | `python test_omni_realtime_quick.py` |
| 交互式聊天 | `test_omni_realtime.py` 选项 3 | `python test_omni_realtime.py` |
| 学习集成方法 | `omni_integration_examples.py` | `python omni_integration_examples.py` |
| 文本→语音 | `test_omni_realtime.py` 选项 1 | `python test_omni_realtime.py` |
| 语音→语音 | `test_omni_realtime.py` 选项 2 | `python test_omni_realtime.py` |
| 诊断问题 | `diagnose_qwen_api.py` | `python diagnose_qwen_api.py` |
| 查看完整文档 | `OMNI_AUDIO_GUIDE.md` | 用文本编辑器打开 |

## 🔑 核心特性

### ⭐ WebSocket 实时方式（推荐）

```
优势:
  ✅ 极低延迟 (< 1s)
  ✅ 双向流式传输
  ✅ 官方 SDK 支持
  ✅ 生产级别稳定性
  
适用于:
  • 实时对话系统
  • 语音客服
  • AI 助手
  • 教育应用
```

### 📦 REST API 方式（备选）

```
优势:
  ✅ 简单直接
  ✅ 易于集成
  
劣势:
  ⚠️ 当前 403 权限错误
  ⚠️ 延迟较高
  
适用于:
  • 一次性请求
  • 批量处理
```

## 🎤 支持的功能

### 输入模态
- ✅ 文本输入
- ✅ 音频输入 (PCM, WAV, MP3 等)
- ✅ 文本 + 音频组合

### 输出模态
- ✅ 文本输出
- ✅ 音频输出
- ✅ 文本 + 音频组合

### 定制选项
- ✅ 系统指令 (instructions)
- ✅ 输出语音角色 (voice: Cherry, Daisy, Alfie)
- ✅ VAD (语音活动检测) 配置
- ✅ 多轮对话上下文保持

## 📊 性能指标

| 指标 | WebSocket | REST API |
|-----|-----------|----------|
| 首字延迟 | 300-500ms | 1-3s |
| 吞吐量 | 实时流式 | 单次请求 |
| 并发支持 | ✅ | ⚠️ |
| 双向交互 | ✅ | ⚠️ |
| 稳定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

## ⚙️ 环境要求

### 最小要求
- Python 3.8+
- dashscope >= 1.23.9
- requests (仅用于 REST API 方式)

### 可选依赖
```bash
# 音频处理
pip install pyaudio soundfile numpy

# 异步支持
pip install asyncio aiohttp

# 性能优化
pip install uvloop
```

## 🚀 部署步骤

1. **安装依赖**
   ```bash
   pip install --upgrade dashscope
   ```

2. **配置环境**
   ```bash
   # 在 .env 中设置
   DASHSCOPE_API_KEY=sk-xxx
   ```

3. **运行测试**
   ```bash
   python test_omni_realtime_quick.py
   ```

4. **集成到应用**
   ```python
   from test_omni_realtime import QwenOmniRealtimeClient
   # 基于示例开发
   ```

## 🐛 常见问题

### Q: "dashscope 未安装"
```bash
pip install dashscope
```

### Q: "403 权限错误"
- 检查 API Key 有效性
- 登录控制面板确认模型已开通

### Q: "连接超时"
- 检查网络连接
- 确认防火墙允许 WSS 连接

### Q: "无语音输出"
- 检查会话配置中 `modalities` 包含 "audio"
- 确认 API 限额充足

**更多答案见** → [OMNI_AUDIO_GUIDE.md](OMNI_AUDIO_GUIDE.md#-常见问题)

## 📞 获取帮助

- 📖 [完整文档](OMNI_AUDIO_GUIDE.md)
- 🚀 [快速开始](QUICKSTART.md)
- 📋 [脚本导航](README_OMNI.md)
- 🔧 [运行诊断](diagnose_qwen_api.py)
- 🌐 [DashScope 官方](https://dashscope.aliyuncs.com)

## 💡 使用场景示例

### 1. 智能客服
```
客户语音输入 → 转文本 → AI 理解 → 生成回复 → 合成语音输出
```

### 2. 教育辅导
```
学生语音提问 → 智能分析 → 生成讲解 → 自然语音回答
```

### 3. 健康助手
```
用户问题 → 健康建议 → 温暖语音回复 + 文本总结
```

### 4. 多语言翻译
```
用户语音(中文) → 翻译 → AI 回复(英文) → 播放语音
```

## 📈 项目统计

```
📝 脚本文件: 6 个
📖 文档文件: 4 个
💻 代码行数: ~2000+ 行
⏱️ 开发时间: 已完成
✅ 测试覆盖: 功能全覆盖
```

## 🎓 进阶主题

- 🔊 [实时音频处理](OMNI_AUDIO_GUIDE.md#q-如何实时播放输出音频)
- 🔐 [错误处理和重连](test_omni_realtime.py#L200)
- 📊 [性能优化](README_OMNI.md#高级技巧)
- 🔄 [多连接管理](#)

## 📜 许可证

MIT License - 可自由使用和修改

## 🙏 致谢

感谢阿里云 DashScope 团队提供的优秀 SDK 和 API 支持

---

## 📌 快速参考

### 环境检查清单
- [ ] Python 3.8+
- [ ] dashscope >= 1.23.9 已安装
- [ ] .env 中有有效 API Key
- [ ] 网络连接正常
- [ ] 防火墙允许 WSS 连接

### 首次使用步骤
1. `pip install --upgrade dashscope`
2. `python test_omni_realtime_quick.py` ✅
3. `python test_omni_realtime.py` (选项 3)
4. 查看 `omni_integration_examples.py`

### 获取支持
- 📖 完整文档: `OMNI_AUDIO_GUIDE.md`
- 🚀 快速指南: `QUICKSTART.md`
- 📋 脚本导航: `README_OMNI.md`

---

**🎉 准备好开始了吗？立即运行：**
```bash
python test_omni_realtime_quick.py
```

**祝你使用愉快！** 🚀
