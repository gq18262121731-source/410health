# 多智能体协作总体规划（中文）

Last updated: 2026-03-22

## 1. 目的

这份文档用于：

- 统一当前优先级
- 统一角色边界
- 统一任务派发与上报规则
- 帮助所有智能体先看全局，再执行各自任务

## 2. 当前阶段

当前项目已经进入：

**前端统一视觉逻辑 + 页面拆分 + 演示收口 + 对话/报告模型分离**

当前主重点不是继续堆新功能，而是：

1. 登录页定稿
2. 登录/注册链拆成小页面
3. 登录页视觉基线扩展到全站
4. 后端、测试继续护航

## 3. 当前优先级

### 第一优先级

- `OM-010`
- `HM-008`
- `AG-004`
- `BE-023`
- `FE-014`
- `TE-022`

### 第二优先级

- `FE-011`
- `FE-012`
- `FE-013`

### 第三优先级

- `UI-005`
- `UI-006`
- `UI-007`

### 第四优先级

- `BE-016` ~ `BE-020`

### 第五优先级

- `BE-021`
- `BE-022`

### 当前 blocked

- `TE-020`

## 4. 当前全站统一视觉逻辑

当前已经不再使用“没有参考图就完全不能推进页面”的旧口径。  
现在的策略是：

- 登录页作为视觉基线
- 其它页面沿用同一视觉系统扩展
- 不允许每页重新发明一套风格

已确认的统一基线：

- 绿色主基调
- 白色 / 淡绿色 / 淡蓝色层级
- 轻玻璃拟态卡片
- 医疗科技感但不过分炫技
- 中文优先

## 5. 模型展示新规则

新增有效要求：

- 普通对话与正式健康报告必须在前端分开展示
- 当前已经进一步升级为：
  - 允许新增内部模型路由
  - 健康报告模型应真正独立出来
  - 健康报告模型应调用健康模型来生成规范式报告

这条规则需要前端、UI、OM、AG 后续共同遵守。

## 6. 上报门槛

- 没有上一轮完整上报，不派下一轮
- 上报必须先审核，再继续派发

统一上报格式：

1. 完成情况
2. 关键代码改动
3. 实际执行命令与结果
4. 当前风险 / 阻塞
5. 是否需要通知其他角色
6. 任务板应如何调整

## 7. 角色阅读顺序

所有角色先读：

1. `docs/dispatcher-self-workflow-zh.md`（我自己优先读；其他角色可略过）
1. `docs/coordination-master-plan-zh.md`
2. `docs/business-and-dispatch-overview-zh.md`
3. `docs/collaboration-gap-task-board.md`
4. `docs/next-agent-handoff.md`
5. 自己的角色文档
6. 再读相关代码

## 8. 当前角色文档

- `docs/coordination-fe-frontend-zh.md`
- `docs/coordination-ui-designer-zh.md`
- `docs/coordination-be-backend-zh.md`
- `docs/coordination-te-test-zh.md`
- `docs/coordination-dr-device-zh.md`
- `docs/coordination-ag-agent-zh.md`
- `docs/coordination-om-offline-model-zh.md`
- `docs/coordination-hm-health-model-zh.md`

## 9. 当前三件最值得盯的事

1. 登录页是否真正定稿
2. 登录/注册链是否完成小页面拆分
3. 统一视觉基线是否开始扩展到业务页
