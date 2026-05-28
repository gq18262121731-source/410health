# LLM Fine-tuning Console Handoff

This repository is a minimal handoff package for the model fine-tuning page and its supporting runtime. It is intentionally scoped to fine-tuning only.

## What Is Included

- `drop-in/frontend/vue-dashboard/src/views/ModelFinetunePage.vue`
  - The polished model fine-tuning operation page.
  - Uses the existing Vue 3 + Vite + lucide-vue-next stack.
- `drop-in/backend/api/model_finetune_api.py`
  - FastAPI routes for the fine-tuning overview, capability probe, dataset export, evaluation gates, and adapter registry.
- `drop-in/backend/services/model_finetune_service.py`
  - Backend service that reads fine-tuning assets and runs bounded scripts.
- `drop-in/scripts/*model_tuning*`
  - LLaMA-Factory capability detection and 7860 WebUI launcher.
- `drop-in/configs/llm_finetune/*`
  - Training templates, dataset registry, adapter routes, and GPU deployment references.
- `drop-in/evals/health_llm/*`
  - Small evaluation gate examples.
- `drop-in/data/llm_finetune/*`
  - Small seed JSONL datasets for local verification.

## What Is Not Included

- No `node_modules`.
- No Python virtual environments or conda environments.
- No model weights.
- No camera, wristband, database dump, or unrelated system code.
- No full project history.

## Expected Host Project

The receiving project should already have:

- Vue 3 + Vite frontend.
- FastAPI backend.
- A dependency provider similar to `get_model_finetune_service()`.
- LLaMA-Factory source at `D:\Program\LLaMA-Factory`, or an equivalent path passed to the startup script.
- A conda environment named `llamafactory` for model tuning.

The source system used:

- fine-tuning env: `llamafactory`
- backend env: `health`
- LLaMA-Factory root: `D:\Program\LLaMA-Factory`
- tuning console URL: `http://127.0.0.1:7860`

## Quick Apply

From this package root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\apply-drop-in.ps1 -TargetRoot "D:\path\to\their-project"
```

Then in the target project:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_model_tuning_console.ps1
```

Open:

```text
http://127.0.0.1:7860
```

## Verification

Run these from the target project after applying:

```powershell
# Backend health
curl http://127.0.0.1:8000/healthz

# Fine-tuning capability API
curl http://127.0.0.1:8000/api/v1/model-finetune/capabilities

# Frontend checks
cd frontend\vue-dashboard
npm run typecheck
npm run lint
npm run build
```

Expected capability highlights:

- `llamafactory: true`
- `torch: true`
- `peft: true`
- `trl: true`
- `bitsandbytes: true`
- `datasets: true`
- `evaluate: true`
- `gradio: true`
- `native_ready.webui: true`
- `native_ready.sft_lora: true`
- `native_ready.qlora_4bit_8bit: true`

## Integration Notes

See [docs/HANDOFF_ZH.md](docs/HANDOFF_ZH.md) for the Chinese handoff guide.

