# 410health 微调数据集说明

本目录随主系统一起上传，用于支撑模型微调页面中的“数据集”选择和预览功能。当前仓库只包含轻量示例数据、健康照护领域数据和数据索引，不包含任何模型权重、训练 checkpoint 或运行缓存。

## 已包含的数据

| 数据集标识 | 文件 | 用途 |
| --- | --- | --- |
| `health_monitoring_single` | `single_turn_monitoring_focus_zh_medical.jsonl` | 单轮健康监测问答微调 |
| `health_monitoring_multi` | `multi_turn_monitoring_focus_zh_medical.jsonl` | 多轮健康监测对话微调 |
| `health_public_single` | `single_turn_public_zh_medical.jsonl` | 单轮通用健康科普问答 |
| `health_public_multi` | `multi_turn_public_zh_medical.jsonl` | 多轮通用健康科普对话 |
| `identity` | `identity.json` | 系统身份与角色表达示例 |
| `alpaca_zh_demo` / `alpaca_en_demo` | `alpaca_zh_demo.json` / `alpaca_en_demo.json` | 指令微调格式示例 |
| `dpo_zh_demo` / `dpo_en_demo` | `dpo_zh_demo.json` / `dpo_en_demo.json` | 偏好优化格式示例 |
| `glaive_toolcall_zh_demo` / `glaive_toolcall_en_demo` | 对应 JSON 文件 | 工具调用格式示例 |
| `mllm_*_demo` | 对应 JSON 文件与 `mllm_demo_data/` | 多模态格式示例 |
| `wiki_demo` / `c4_demo` | `wiki_demo.txt` / `c4_demo.jsonl` | 预训练数据格式示例 |

数据集注册文件为 `dataset_info.json`。微调页面会从这里读取可选数据集；新增数据时，请先把数据文件放入本目录，再在 `dataset_info.json` 中添加对应配置。

## 推荐数据格式

### 单轮或多轮对话

```json
{
  "messages": [
    { "role": "user", "content": "老人夜间心率偏高应该如何处理？" },
    { "role": "assistant", "content": "建议先观察是否伴随胸闷、气短、出汗等症状..." }
  ]
}
```

### 指令微调

```json
{
  "instruction": "根据健康监测记录给出照护建议",
  "input": "心率 103，血氧 96%，夜间频繁起身",
  "output": "建议关注睡眠质量和夜间活动安全..."
}
```

## 上传约束

- 可以上传：本目录下的数据集、格式示例、数据索引。
- 不要上传：模型权重、训练输出、缓存、日志、隐私原始数据。
- 如果数据来自真实业务，请先完成脱敏处理，删除姓名、电话、身份证号、详细住址等个人敏感信息。

## 常见操作

1. 把新数据文件放入 `model_tuning/data/`。
2. 在 `dataset_info.json` 中增加数据集条目。
3. 启动微调页面，在“数据集”下拉框中选择新数据。
4. 使用“预览数据集”确认字段解析正确。
