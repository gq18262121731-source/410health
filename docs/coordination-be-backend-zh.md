# Backend Engineer 协作文档（中文）

Last updated: 2026-03-22

## 先读

1. `docs/coordination-master-plan-zh.md` 中的：
   - 当前优先级
   - 模型展示新规则
2. `docs/business-and-dispatch-overview-zh.md` 中的：
   - 对话模型与报告模型的新要求
   - 当前后端真实可用能力
3. `docs/collaboration-gap-task-board.md`
4. `docs/next-agent-handoff.md`
5. `docs/agent-collaboration-contract.md`

## 你的当前任务

- `BE-016`
- `BE-017`
- `BE-018`
- `BE-019`
- `BE-020`
- `BE-021`
- `BE-022`
- `BE-023`

## 当前优先级

1. 先护航“对话模型 / 报告模型分离”所需的内部配置与路由
2. 再护航前端当前演示链
3. 再做数据库硬化
4. 最后做网关实现

## 当前必须保证可用的接口

- `/api/v1/auth/login`
- `/api/v1/auth/register/elder`
- `/api/v1/auth/register/family`
- `/api/v1/auth/register/community-staff`
- `/api/v1/care/access-profile/me`
- `/api/v1/chat/report/device`

## 当前新增要求

- 允许新增内部模型路由与内部模型配置
- 报告模型需要真正独立出来
- 报告模型应调用健康模型提供的内部上下文
- 但不要轻易改公共 report schema

## 不要做的事

- 不要因为前端视觉问题随意改公共字段
- 不要把运行态问题误报成代码问题
- 不要继续让报告与对话共用同一内部策略而不明确上报

## 文档维护职责

- 每完成一轮工作，先更新本文档，再上报
- 如果任务优先级或契约结论变化，必须先写进本文档
- 需要明确写出：
  - 当前任务
  - 当前不要做什么
  - 依赖谁
  - 谁依赖你
- 没有文档更新和完整上报，不进入下一轮任务

## 上报格式

1. 完成情况
2. 关键代码改动
3. 实际执行命令与结果
4. 当前风险 / 阻塞
5. 是否需要通知 FE / TE / AG / OM / HM
6. 任务板应如何调整
