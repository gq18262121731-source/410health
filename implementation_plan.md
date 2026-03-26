# Family App 监测界面重构计划

本次重构旨在优化 Flutter 子女端（Family App）的单设备实时监测界面（[DeviceDetailScreen](file:///d:/code/health/mobile/flutter_app/lib/features/health/screens/device_detail_screen.dart#9-17)），使其能更加紧凑地展示数据并提供更详尽的多参数实时曲线对比，视觉上贴近 Vue 社区大屏的风格。

## Proposed Changes

### 1. [DeviceDetailScreen](file:///d:/code/health/mobile/flutter_app/lib/features/health/screens/device_detail_screen.dart#9-17) 布局与样式重构
#### [MODIFY] [lib/features/health/screens/device_detail_screen.dart](file:///d:/code/health/mobile/flutter_app/lib/features/health/screens/device_detail_screen.dart)
- **指标卡片紧凑化 (Compact Metrics)**: 
  - 取代原本占据大范围空间的 2x3 `GridView`，改为在健康分下方使用紧凑的横向 [Wrap](file:///d:/code/health/mobile/flutter_app/lib/features/health/screens/device_detail_screen.dart#363-390) 布局或是横向滚动列表（类似于小 Chip 或紧凑卡片）。
  - 各个卡片字号、间距缩减，确保能在小屏幕上一目了然。
- **四项独立实时曲线 (4 Vertical Charts)**: 
  - 移除原先混合展示心率/血氧的单图表。
  - 新增四个独立的 `LineChart` 组件，纵向排列分布在下方：
    1. **心率 (Heart Rate)**
    2. **血氧 (Blood Oxygen)**
    3. **血压 (Blood Pressure)** - (需解析收缩压 SBP / 舒张压 DBP，画双折线)
    4. **体温 (Temperature)**

### 2. Provider 数据解析支持 (Agent & LLM Fixes)
#### [MODIFY] [agent/community_langgraph_agent.py](file:///d:/code/health/agent/community_langgraph_agent.py)
- **更新 [_build_llm](file:///D:/code/health/agent/community_langgraph_agent.py#1397-1414)**: 将 `streaming=False` 改为参数化，默认为 `True`，确保流式输出正常工作。
- **优化 [_build_prompt](file:///D:/code/health/agent/community_langgraph_agent.py#1381-1396)**: 移除 120 字的硬性限制，改用更详尽、专业的系统提示词（System Prompt），要求包含风险等级、指标分析、原因及建议。
- **更新 [_generate_answer](file:///D:/code/health/agent/community_langgraph_agent.py#1318-1351)**: 即使非流式调用也使用 `streaming=False` 的 LLM 实例，保证调用一致性。
- **完善 [stream_analyze_device](file:///d:/code/health/agent/community_langgraph_agent.py#158-251)**: 确保使用正确的 LLM 实例和 `llm.stream()` 方法。

#### [MODIFY] [backend/api/chat_api.py](file:///d:/code/health/backend/api/chat_api.py)
- **强制使用 Qwen**: 将所有 [DeviceAnalysisRequest](file:///d:/code/health/backend/api/chat_api.py#20-27) 和 [CommunityAnalysisRequest](file:///d:/code/health/backend/api/chat_api.py#34-59) 的默认 [mode](file:///d:/code/health/backend/config.py#331-338)/[provider](file:///D:/code/health/agent/community_langgraph_agent.py#1455-1460) 改为 [qwen](file:///d:/code/health/backend/config.py#303-306)。
- **新增流式端点**: 确保 `/analyze/device/stream` 正确映射到 [stream_analyze_device](file:///d:/code/health/agent/community_langgraph_agent.py#158-251)。

### 3. Flutter 客户端对齐 (Stream & Formatting)
- [x] **NDJSON 支持**: [ApiClient](file:///d:/code/health/mobile/flutter_app/lib/core/network/api_client.dart#4-58) 已添加 [postStream](file:///d:/code/health/mobile/flutter_app/lib/core/network/api_client.dart#45-55) 支持。
- [x] **流式 UI**: [AiChatDialog](file:///d:/code/health/mobile/flutter_app/lib/features/agent/widgets/ai_chat_dialog.dart#5-13) 已更新为支持打字机效果。
- [x] **样式优化**: 使用 `RichText` 渲染带光标的答案，解决之前的 JSON 格式显示问题。

## Verification Plan

### Manual Verification
1. 运行 `flutter run` 并在 App 中进入任意设备详情页。
2. 确认健康分下方有紧凑分布的各项参数数值。
3. 确认页面往下滚动能看到 4 张纵向分布的曲线图表。
4. 确认模拟数据更新时，所有 4 张曲线都会同步绘制（包括血压双线）。
