# 智慧康养模型微调子系统

本目录是 `410health` 主系统的模型微调子系统，用于在本地完成领域数据训练、评估预测、模型对话验证和模型导出。页面已经接入主系统的“模型微调”入口，默认地址为：

```text
http://127.0.0.1:7860
```

## 仓库内容

已随仓库上传：

- `src/`：微调系统核心代码
- `data/`：可直接使用的示例数据集和智慧康养领域数据集
- `examples/`：训练、推理、合并和导出配置样例
- `requirements/`：可选加速组件依赖清单
- `LLAMA_FACTORY_OPERATION_GUIDE_ZH.md` / `操作文档.md`：中文操作说明

不会上传：

- `models/`：本地基础模型和合并后的模型
- `saves/`：训练输出、LoRA 适配器、checkpoint、optimizer 状态
- `llamaboard_cache/`、`offload/`、`hf_cache/`、`ms_cache/`：运行缓存
- `*.safetensors`、`*.pt`、`*.bin`、`*.ckpt`、`*.gguf` 等权重文件

## 环境安装

建议使用独立 conda 环境，Python 版本使用 3.11：

```powershell
conda create -n llamafactory python=3.11 -y
conda activate llamafactory
python -m pip install -e .
```

如果需要 CUDA 版 PyTorch，请先按本机 CUDA 版本安装对应 PyTorch，再执行 `pip install -e .`。

## 模型准备

模型文件不随 GitHub 仓库上传。下载项目后，请自行准备基础模型，并放到：

```text
model_tuning/models/
```

例如：

```text
model_tuning/models/train_model/
```

然后在页面的“模型路径”里填写该目录，或填写 Hugging Face / ModelScope 的模型标识符。

## 数据集

数据集已经随仓库上传到：

```text
model_tuning/data/
```

其中智慧康养领域数据集包括：

- `single_turn_public_zh_medical.jsonl`
- `single_turn_monitoring_focus_zh_medical.jsonl`
- `multi_turn_public_zh_medical.jsonl`
- `multi_turn_monitoring_focus_zh_medical.jsonl`

数据集索引配置位于：

```text
model_tuning/data/dataset_info.json
```

## 启动微调页面

在本目录下执行：

```powershell
conda activate llamafactory
cd model_tuning
$env:GRADIO_SERVER_NAME="127.0.0.1"
$env:GRADIO_SERVER_PORT="7860"
python -m llamafactory.cli webui
```

启动后打开：

```text
http://127.0.0.1:7860
```

主系统前端会通过 iframe 嵌入这个地址。

## 主系统接入

主系统前端默认读取：

```text
VITE_MODEL_TUNING_URL=http://127.0.0.1:7860
```

如需修改微调服务地址，可在主系统前端环境变量中设置 `VITE_MODEL_TUNING_URL`。

## 许可证说明

本子系统基于 Apache-2.0 许可的开源微调框架进行二次开发，并已做主系统集成、界面白标、中文化和智慧康养业务数据适配。保留 `LICENSE` 与必要的开源许可信息。
