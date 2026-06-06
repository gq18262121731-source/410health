# Qwen Omni 实时语音 - 快速开始指南

## 📦 安装步骤

### 1. 安装 DashScope SDK

```bash
# 安装或升级到最新版本
pip install --upgrade dashscope

# 验证版本 (需要 >= 1.23.9)
python -c "import dashscope; print(f'Version: {dashscope.__version__}')"
```

### 2. 验证环境配置

确保 `.env` 文件中有以下配置:

```
DASHSCOPE_API_KEY=sk-xxxxxxxxx
# 或
QWEN_API_KEY=sk-xxxxxxxxx
```

## 🚀 最快速的测试

运行以下命令快速测试连接:

```bash
python test_omni_realtime_quick.py
```

**预期输出:**
```
✓ API Key 已设置
✓ dashscope 库已安装
✓ WebSocket 连接成功
✓ 连接已建立
📤 已发送文本
⏳ 等待响应...
🤖 [AI 的响应文本会在这里显示]
✅ 连接测试成功！
```

## 💬 开始交互式对话

```bash
python test_omni_realtime.py
```

然后选择选项 **3** 进入交互模式:

```
输入你的问题，按 Enter 发送
输入 'exit' 或 'quit' 退出
输入 'save' 保存输出音频

👤 您: 你好，请介绍自己
🤖 我是阿里云开发的一个 AI 助手...
👤 您: (继续对话)
```

## 📚 完整示例

查看 `omni_integration_examples.py` 了解如何在应用中集成:

```bash
python omni_integration_examples.py
```

包含 5 个实际使用示例:
1. 简单问答
2. 多轮对话
3. 不同语音角色
4. 流式响应
5. 睡眠监测系统集成

## 🎯 常见用途

### 用途 1: 文本问答 + 语音反馈

```python
from omni_integration_examples import SimpleAudioTester

tester = SimpleAudioTester(
    instructions="你是一位知识渊博的导游",
    voice="Cherry"
)

tester.start()
response = tester.ask("北京有哪些必去景点？")
print(response)
tester.close()
```

### 用途 2: 实时对话系统

基于 `test_omni_realtime.py` 的交互模式开发

### 用途 3: 语音客服系统

结合 `OmniRealtimeClient` 实现语音输入/输出的客服

## ⚙️ 关键参数

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `model` | 模型名称 | `qwen3.5-omni-plus-realtime` |
| `voice` | 输出语音角色 | `Cherry`, `Daisy`, `Alfie` |
| `instructions` | 系统提示词 | `你是一个旅游顾问` |
| `threshold` | VAD 敏感度 (0-1) | `0.5` |
| `silence_duration_ms` | 静音触发时间 (ms) | `800` |

## 🔧 故障排除

### 问: 提示 "dashscope 未安装"

```bash
pip install dashscope
```

### 问: 连接超时

检查:
1. 网络连接
2. 防火墙是否允许 WSS (WebSocket Secure)
3. API Key 是否正确

### 问: 403 权限错误

- 检查 API Key 是否过期
- 登录 DashScope 控制面板确认模型已开通
- 检查账户余额

### 问: 无法识别中文

- 检查音频的采样率和格式
- 确保音频清晰度足够
- 在提示词中强调要求 (e.g., "请用中文回复")

## 📖 详细文档

完整文档见: [OMNI_AUDIO_GUIDE.md](OMNI_AUDIO_GUIDE.md)

## 🎓 学习路径

1. ✅ **第 1 步** - 运行快速测试
   ```bash
   python test_omni_realtime_quick.py
   ```

2. ✅ **第 2 步** - 尝试交互模式
   ```bash
   python test_omni_realtime.py
   # 选择选项 3
   ```

3. ✅ **第 3 步** - 查看集成示例
   ```bash
   python omni_integration_examples.py
   ```

4. ✅ **第 4 步** - 基于示例开发自己的应用

## 📞 获取帮助

- [DashScope 官方文档](https://dashscope.aliyuncs.com)
- [Qwen 模型中心](https://qwen.aliyun.com)
- 运行诊断工具: `python diagnose_qwen_api.py`

---

**祝你使用愉快！🎉**
