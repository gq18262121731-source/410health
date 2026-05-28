# 大模型微调页面交接文档

## 交接目标

把当前系统中已经调整完成的“大模型微调运营面板”和 LLaMA-Factory 7860 工作台接入能力，交给其他成员用于替换他们项目里较旧或较粗糙的微调页面。

本包只包含微调相关内容，不包含完整系统。

## 目录说明

所有可复制文件都在 `drop-in` 目录中，并保留原项目路径。

建议程序员按路径覆盖或合并：

```text
drop-in/
  frontend/vue-dashboard/src/views/ModelFinetunePage.vue
  backend/api/model_finetune_api.py
  backend/services/model_finetune_service.py
  scripts/model_tuning_capabilities.ps1
  scripts/model_tuning_console_entry.py
  scripts/start_model_tuning_console.ps1
  scripts/start_all_local_stack.ps1
  scripts/export_llm_finetune_dataset.py
  scripts/eval_finetuned_llm.py
  configs/llm_finetune/
  evals/health_llm/
  data/llm_finetune/
```

## 页面效果

`ModelFinetunePage.vue` 已经完成视觉升级：

- 和智慧康养系统的蓝绿配色呼应。
- 训练环境、数据层、评测门禁、Adapter 路由使用不同语义色。
- 支持嵌入 `http://127.0.0.1:7860` 的 LLaMA-Factory 工作台。
- 保持运维页面的密度和可扫读性，没有做成营销页。

## 接入步骤

### 1. 复制文件

在本包根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\apply-drop-in.ps1 -TargetRoot "D:\path\to\their-project"
```

也可以手动复制 `drop-in` 下的文件到目标项目对应路径。

### 2. 注册后端路由

如果目标项目还没有注册路由，需要在 FastAPI 主入口中加入：

```python
from backend.api.model_finetune_api import router as model_finetune_router

app.include_router(model_finetune_router, prefix=settings.api_v1_prefix)
```

### 3. 注册服务依赖

目标项目需要提供：

```python
get_model_finetune_service()
```

参考当前项目的依赖注入方式，返回：

```python
ModelFinetuneService(project_root=<project_root>, llama_factory_root=Path("D:/Program/LLaMA-Factory"))
```

如果目标项目已有依赖容器，只需要把 `ModelFinetuneService` 接进去。

### 4. 准备 LLaMA-Factory 环境

推荐使用独立 conda 环境，不要复用业务后端环境。

当前系统使用：

```text
conda env: llamafactory
LLaMA-Factory root: D:\Program\LLaMA-Factory
WebUI: http://127.0.0.1:7860
```

启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_model_tuning_console.ps1
```

如果 LLaMA-Factory 不在默认路径：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_model_tuning_console.ps1 `
  -CondaEnv llamafactory `
  -LLaMAFactoryRoot "D:\Program\LLaMA-Factory" `
  -Port 7860
```

### 5. 前端环境变量

默认微调工作台地址为：

```text
http://127.0.0.1:7860
```

如需修改，可设置：

```env
VITE_MODEL_TUNING_URL=http://127.0.0.1:7860
```

## 验证步骤

### 后端接口

```powershell
curl http://127.0.0.1:8000/api/v1/model-finetune/overview
curl http://127.0.0.1:8000/api/v1/model-finetune/capabilities
```

### LLaMA-Factory 工作台

```powershell
curl http://127.0.0.1:7860
```

### 前端质量检查

```powershell
cd frontend\vue-dashboard
npm run typecheck
npm run lint
npm run build
```

## 常见问题

### 页面显示 7860 工作台不可访问

先确认控制台是否启动：

```powershell
Get-NetTCPConnection -LocalPort 7860 -State Listen
```

如果没有监听，启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_model_tuning_console.ps1
```

### capabilities 里 `llamafactory: false`

检查 `D:\Program\LLaMA-Factory\src` 是否存在。启动脚本会自动把这个路径加入 `PYTHONPATH`。

### 不建议直接用后端业务环境微调

微调依赖和业务后端依赖经常冲突。当前方案默认使用 `llamafactory` 环境，避免破坏后端服务。

### Docker 项显示不可用

这不影响 Windows 原生 WebUI、SFT、LoRA、QLoRA 和 DPO 基础流程。DeepSpeed、FlashAttention、vLLM、Unsloth 更适合 Docker 或 WSL2。

## 交接边界

本交接包负责：

- 微调运营页面 UI。
- 微调能力检测接口。
- LLaMA-Factory 7860 工作台启动。
- 数据导出、评测门禁、Adapter 路由的管理入口。

本交接包不负责：

- 真实模型权重分发。
- 大规模训练数据迁移。
- 摄像头、手环、告警、移动端等非微调模块。
- GitHub Actions 或 CI 的完整迁移。

