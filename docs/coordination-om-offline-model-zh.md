# Offline Model Engineer 协作文档（中文）

Last updated: 2026-03-22

## 先读

1. `docs/coordination-master-plan-zh.md` 中的：
   - 当前优先级
   - 模型展示新规则
2. `docs/business-and-dispatch-overview-zh.md` 中的：
   - 对话模型与报告模型的新要求
3. `docs/collaboration-gap-task-board.md`
4. `docs/next-agent-handoff.md`
5. `docs/local-model-runtime.md`

## 当前状态

- 当前新增开放任务：`OM-010`
- 不再是纯待命

## 当前职责

1. 把普通对话模型与健康报告模型分成两套内部路由策略
2. 允许新增内部配置，例如 `local_report_model`
3. 保持：
   - 问答链路有限长策略
   - 报告链路不受该限长策略误伤

## 当前必须明确的边界

- 可以新增内部模型路由
- 可以新增内部模型配置
- 不要擅自改 public report schema
- 不要把对话限长规则误套到正式报告

## 文档维护职责

- 每完成一轮工作，先更新本文档，再上报
- 如果当前模型路由策略变化，必须先写进本文档
- 需要明确写出：
  - 当前任务
  - 当前不要做什么
  - 依赖谁
  - 谁依赖你
- 没有文档更新和完整上报，不进入下一轮任务

## 上报格式

1. 完成情况
2. 是否需要继续由 OM 介入
3. 实际执行命令与结果
4. 风险 / 阻塞
5. 是否需要通知其他角色
6. 任务板应如何调整
