# .env 配置完成后的后续任务指南

## 📋 当前状态

✅ **已完成：**
- .env 文件已配置
- API 密钥有效（sk-67d1be1cac0649b9a8839d2328bbb845）
- 可以访问 qwen3.5-flash 模型（兼容模式 API）

❌ **未完成：**
- qwen3.5-omni-plus 在兼容模式 API 中无权限（403）
- qwen3.5-omni-plus-realtime WebSocket API 认证失败（401）

## 🔍 问题分析

### 问题 1: qwen3.5-omni-plus 无权限 (403)

**原因：** 
- 你的 API 密钥在兼容模式 API 中没有 Omni 模型的访问权限
- Omni 是高级功能，可能需要特殊授权或付费版本

**解决方案：**
```
1. 登录 https://dashscope.aliyuncs.com/
2. 检查账户配额和模型权限
3. 联系阿里云服务支持申请 Omni 模型权限
4. 或者使用 qwen3.5-flash 替代
```

### 问题 2: WebSocket realtime API 认证失败 (401)

**原因：**
- WebSocket 连接的认证方式与 HTTP API 不同
- 可能需要特殊的认证令牌或方法

**解决方案：**
```
方案 A: 联系阿里云获取 Omni 权限
方案 B: 使用 HTTP 兼容 API（如果权限允许）
方案 C: 参考官方文档了解最新认证方式
```

## 📱 Flutter 移动端 - 当前配置

### ✅ 已实现的功能

在 `mobile/flutter_app` 中已配置了完整的语音交互功能：

1. **WebSocket 服务** (`lib/features/voice/services/omni_realtime_service.dart`)
   - WebSocket 连接管理
   - 音频编码和发送
   - 事件流处理

2. **状态管理** (`lib/features/voice/providers/omni_voice_provider.dart`)
   - 完整生命周期
   - 状态转换
   - 错误处理

3. **UI 组件** (`lib/features/voice/widgets/` 和 `lib/features/voice/screens/`)
   - 语音交互 Widget
   - 完整屏幕
   - 老人友好界面

4. **集成** (`lib/main.dart`, `elder_home_screen.dart`)
   - Provider 注册
   - 导航按钮
   - 完整工作流

### 🔧 Flutter 配置检查项

```bash
cd mobile/flutter_app

# 检查依赖
flutter pub get

# 验证编译
flutter analyze
flutter build apk --analyze-size

# 本地测试
flutter run
```

## 🚀 后续任务清单

### 任务 1: 验证后端 API 配置

**状态：** 🔴 部分完成

需要做的事：
- [ ] 确认 API 密钥有 Omni 模型权限
- [ ] 联系阿里云申请权限（如需要）
- [ ] 获取 WebSocket 认证的正确方法

**验证命令：**
```bash
# 测试 qwen3.5-flash（目前可用）
python test_api_key.py

# 如果获得 Omni 权限后，测试 WebSocket
python test_omni_realtime_api.py
```

### 任务 2: 后端集成（可选）

**状态：** ⚪ 未开始

如果要在后端集成 Omni 功能：

1. **创建后端 API 端点** (backend/api/voice.py)
   ```python
   # POST /api/voice/chat
   # 接收音频或文本，返回 AI 响应
   ```

2. **集成 WebSocket 管理** (backend/services/omni_service.py)
   ```python
   # 管理与 Qwen Omni 的 WebSocket 连接
   # 处理多个并发请求
   ```

3. **添加数据库存储** (database/schema.sql)
   ```sql
   -- 存储对话历史
   -- 存储音频文件
   ```

### 任务 3: 部署 Flutter 移动端

**状态：** 🟡 准备就绪

需要做的事：
- [ ] 配置 Android 权限（AndroidManifest.xml）
- [ ] 配置 iOS 权限（Info.plist）
- [ ] 更新 .env 中的 API 密钥（或用安全存储）
- [ ] 编译 APK/IPA
- [ ] 真机测试

**具体步骤：**

```bash
# 1. 准备
cd mobile/flutter_app
flutter clean
flutter pub get

# 2. 配置权限（检查文件）
# android/app/src/main/AndroidManifest.xml
# ios/Runner/Info.plist

# 3. 编译
flutter build apk --release  # Android
flutter build ios --release  # iOS (需要 macOS)

# 4. 安装测试
flutter run
```

### 任务 4: 测试和验证

**状态：** 🟡 部分就绪

需要做的事：
- [ ] 单元测试（见 tests/VOICE_TESTING_GUIDE.md）
- [ ] 集成测试
- [ ] 真机测试
- [ ] 用户验收测试

**运行测试：**
```bash
# 单元测试
flutter test

# 集成测试
flutter test integration_test/

# 真机测试
flutter run -d <device-id>
```

### 任务 5: 文档和部署

**状态：** ✅ 完成

已创建的文档：
- ✅ `mobile/flutter_app/VOICE_INTEGRATION_GUIDE.md`
- ✅ `mobile/flutter_app/VOICE_SETUP_CHECKLIST.md`
- ✅ `docs/VOICE_ARCHITECTURE.md`
- ✅ `docs/VOICE_DEPLOYMENT_TROUBLESHOOTING.md`
- ✅ `tests/VOICE_TESTING_GUIDE.md`

## 🎯 优先级任务

### 立即（今天）
1. **确认 API 权限** - 检查是否有 Omni 模型权限
2. **更新 Flutter 配置** - 添加正确的 API 端点和密钥
3. **本地编译测试** - 验证 Android/iOS 编译不出错

### 本周
1. **真机测试** - 在实际设备上测试语音功能
2. **权限测试** - 验证麦克风和网络权限请求
3. **集成测试** - 完整的用户交互流程

### 本月
1. **后端集成** - 如果需要后端支持
2. **性能优化** - 如果有性能问题
3. **用户测试** - 老人可用性测试

## 🔧 快速修复清单

### 如果 WebSocket 连接失败 (401)

```python
# 在 .env 中尝试不同的配置
# 选项 1: 使用完整的 Bearer 令牌
QWEN_API_KEY=sk-full-token-here

# 选项 2: 检查 API 基础 URL
QWEN_REALTIME_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/realtime

# 选项 3: 按照官方文档更新认证方式
```

### 如果 Omni 模型无权限 (403)

```python
# 在 .env 中添加备用模型配置
QWEN_FALLBACK_MODEL=qwen3.5-flash  # 开启降级

# 或使用其他模型
QWEN_OMNI_MODEL=qwen2-7b-chat-int4
```

### 如果 Flutter 编译失败

```bash
# 清理和重建
flutter clean
flutter pub get
flutter pub upgrade

# 检查分析
flutter analyze

# 检查编译
flutter build apk --analyze-size
```

## 📞 需要帮助？

### 常见问题

**Q: 为什么显示 403 Access Denied？**
A: API 密钥没有该模型的权限。需要在阿里云账户中申请。

**Q: WebSocket 连接为什么失败 (401)？**
A: 认证方式可能不对，或者密钥无效。参考阿里云官方文档。

**Q: Flutter 编译时找不到依赖？**
A: 运行 `flutter pub get` 和 `flutter pub upgrade`

**Q: 麦克风权限如何申请？**
A: 在 AndroidManifest.xml 和 Info.plist 中配置，首次运行时系统会询问。

### 快速支持链接

- 阿里云 DashScope 文档：https://help.aliyun.com/zh/model-studio/
- Qwen 官方 GitHub：https://github.com/QwenLM/Qwen
- Flutter 官方文档：https://flutter.dev/docs

## 📊 进度跟踪

| 任务 | 状态 | 优先级 | 截止日期 |
|------|------|--------|---------|
| API 权限确认 | 🔴 未完成 | 高 | 今天 |
| Flutter 本地测试 | 🟡 部分 | 高 | 本周 |
| 真机测试 | ✅ 准备就绪 | 高 | 本周 |
| 后端集成 | ⚪ 可选 | 中 | 本月 |
| 性能优化 | ⚪ 可选 | 低 | 本月 |

---

**更新时间：** 2026-04-01  
**相关文件：** .env, test_api_key.py, test_omni_realtime_api.py  
**负责人：** DevOps / Backend Team
