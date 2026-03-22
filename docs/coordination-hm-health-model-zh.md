# Health Model Engineer 协作文档（中文）

Last updated: 2026-03-22

## 先读

1. `docs/coordination-master-plan-zh.md` 中的：
   - 当前优先级
   - 模型展示新规则
2. `docs/business-and-dispatch-overview-zh.md` 中的：
   - 对话模型与报告模型的新要求
3. `docs/collaboration-gap-task-board.md`
4. `docs/next-agent-handoff.md`
5. `docs/health-model-calibration.md`
6. `docs/health-model-demo-scenarios.md`

## 当前状态

- 当前新增开放任务：`HM-008`

## 当前职责

1. 为正式健康报告提供稳定、规范的健康模型上下文
2. 让专属 report-model 路由能直接调用健康模型结果
3. 在不破坏 public report schema 的前提下，提供内部可消费的：
   - 风险评分
   - 异常解释
   - 持续异常状态
   - 报警准备状态

## 再介入重点

- 前端最终展示需要更稳的报告解释
- 报告模型要真正调用健康模型
- 内部报告上下文要规范化、可复用

## 文档维护职责

- 每完成一轮工作，先更新本文档，再上报
- 如果内部报告上下文或协作边界变化，必须先写进本文档
- 需要明确写出：
  - 当前任务
  - 当前不要做什么
  - 依赖谁
  - 谁依赖你
- 没有文档更新和完整上报，不进入下一轮任务

## 上报格式

1. 完成情况
2. 是否还需要 HM 继续介入
3. 实际执行命令与结果
4. 风险 / 阻塞
5. 是否需要通知 FE / AG / TE / OM / BE
6. 任务板应如何调整
