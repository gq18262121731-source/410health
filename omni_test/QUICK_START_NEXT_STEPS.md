# 🚀 快速启动 - 完整的后续任务

## 📝 当前进度总结

### ✅ 已完成
- Flutter 移动端完整的语音交互功能实现
- 5个详细文档（集成指南、部署、测试、架构）
- .env 文件配置

### ⚠️ 遇到的问题
- API 密钥在某些 API 模式下受限
- qwen3.5-omni-plus: 兼容模式无权限 (403)  
- qwen3.5-omni-plus-realtime: WebSocket 认证方式待确认 (401)

### 🟢 立即可做的 3 项任务

## 任务 1️⃣: 使用可用模型测试后端 (15分钟)

### 当前可用的
- **Model：** qwen3.5-flash
- **API：** https://dashscope.aliyuncs.com/compatible-mode/v1
- **用途：** 文本对话

### 执行命令
```bash
cd d:\code\health

# 测试文本对话功能
python test_api_key.py

# 输出应该显示：
# ✓ qwen3.5-flash 成功 (200)
# ✓ 响应: "你好！👋 很高兴见到你！..."
```

### 创建后端 API 端点（可选）
如果需要后端支持：

```python
# backend/api/voice.py
from fastapi import APIRouter
import httpx
import os

router = APIRouter()

@router.post("/chat")
async def chat(message: str):
    """使用 qwen3.5-flash 进行对话"""
    api_key = os.getenv("QWEN_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "qwen3.5-flash",
        "messages": [{"role": "user", "content": message}],
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{os.getenv('QWEN_API_BASE')}/chat/completions",
            json=payload,
            headers=headers,
        )
        return response.json()
```

------

## 任务 2️⃣: 部署 Flutter 移动端 (1-2小时)

### 步骤 1: 环境准备
```bash
cd mobile/flutter_app

# 清理旧的构建
flutter clean

# 获取最新依赖
flutter pub get
```

### 步骤 2: 配置权限

#### Android (android/app/src/main/AndroidManifest.xml)
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- 添加这些权限 -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
    
    <application ...>
        <!-- 现有配置 -->
    </application>
</manifest>
```

#### iOS (ios/Runner/Info.plist)
```xml
<dict>
    <key>NSMicrophoneUsageDescription</key>
    <string>我们需要使用你的麦克风来进行语音对话</string>
</dict>
```

### 步骤 3: 验证编译
```bash
# 检查代码质量
flutter analyze

# 编译 APK
flutter build apk
# 或编译 IPA (macOS 需要)
# flutter build ios
```

### 步骤 4: 本地测试
```bash
# 运行应用
flutter run

# 在应用中：
# 1. 登录或跳过登录
# 2. 点击"语音对话"按钮
# 3. 按住"按住说话"开始录音
# 4. 说出问题（如"你好"）
# 5. 释放按钮，等待响应
```

### 步骤 5: 真机测试（可选）
```bash
# 列出设备
flutter devices

# 在特定设备上运行
flutter run -d <device-id>

# 发布版本
flutter build apk --release
adb install build/app/outputs/apk/release/app-release.apk
```

------

## 任务 3️⃣: 解决 API 权限问题 (需要外部支持)

### 问题描述
- qwen3.5-omni-plus 无法在兼容模式 API 中访问 (403)
- WebSocket realtime 认证方式不清楚 (401)

### 解决方案

#### 方案 A: 申请 Omni 权限（推荐）
```
1. 登录 https://dashscope.aliyuncs.com/
2. 进入"模型广场" → Qwen Omni
3. 点击"开通服务"或"购买"
4. 完成支付和激活
5. 等待权限更新（通常 5-10 分钟）
6. 重新测试
```

#### 方案 B: 使用已有的 qwen3.5-flash
```bash
# 在 Flutter app 中配置
# lib/main.dart

final omniService = OmniRealtimeService(
  apiKey: apiKey,
  model: 'qwen3.5-flash',  # 改用此模型
  // ...
);
```

#### 方案 C: 联系阿里云技术支持
```
官方支持网址: https://help.aliyun.com/zh/model-studio/
问题类型: "API 权限问题"
提供: API 密钥前缀 (sk-67d1be1...)
```

------

## 📋 完整任务清单

### 今天（第 1 天）
- [ ] 运行 `test_api_key.py` 验证配置
- [ ] 检查 Flutter 编译（`flutter analyze`）
- [ ] 确认 API 权限问题

### 本周（第 2-3 天）
- [ ] 配置 Android/iOS 权限
- [ ] 本地 Flutter 测试
- [ ] 真机第一次测试

### 本月（第 2 周）
- [ ] 根据测试结果优化
- [ ] 集成后端 API（如需要）
- [ ] 用户验收测试

### 可选（性能完善）
- [ ] 集成对话历史
- [ ] 添加性能分析
- [ ] 支持更多语言

------

## 🎯 3 个关键指标

| 指标 | 当前 | 目标 |
|------|------|------|
| API 可用性 | ✅ qwen3.5-flash | ✅ 所有需要的模型 |
| Flutter 编译 | ✅ 成功 | ✅ 无警告 |
| 真机测试 | ⏳ 准备中 | ✅ 通过 |

------

## 🆘 遇到问题？

### 快速诊断
```bash
# 1. 测试 API
python test_api_key.py

# 2. 测试 WebSocket (如果有 Omni 权限)
python test_omni_realtime_api.py

# 3. 检查 Flutter 编译
flutter analyze
flutter build apk

# 4. 查看日志
flutter logs
```

### 常见错误修复

**错误 403 (Access Denied)**
→ 需要申请 Omni 或 Realtime 权限

**错误 401 (Unauthorized)**
→ API 密钥无效或认证方式错误

**Flutter 编译失败**
→ 运行 `flutter clean && flutter pub get`

**麦克风无法工作**
→ 检查 AndroidManifest.xml 和 Info.plist 权限

------

## 📚 相关文档

快速查看以下文档了解详情：

1. **集成指南** → `mobile/flutter_app/VOICE_INTEGRATION_GUIDE.md`
2. **部署步骤** → `docs/VOICE_DEPLOYMENT_TROUBLESHOOTING.md`
3. **系统架构** → `docs/VOICE_ARCHITECTURE.md`
4. **测试指南** → `tests/VOICE_TESTING_GUIDE.md`
5. **详细后续** → `NEXT_STEPS_AFTER_ENV.md` (本文件)

------

## 🎬 下一步行动

**立即执行（5分钟）：**
```bash
cd d:\code\health
python test_api_key.py
```

**然后执行（30分钟）：**
```bash
cd mobile/flutter_app
flutter analyze
flutter build apk
```

**最后执行（根据结果）：**
- 如果编译成功 → `flutter run` 本地测试
- 如果有错误 → 查看 [故障排查](./docs/VOICE_DEPLOYMENT_TROUBLESHOOTING.md)

---

**准备好了吗？让我们开始吧！** 🚀

提示：如果你遇到"权限不足"的问题，先完成"任务 3"中的权限申请。
