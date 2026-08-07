# 真实 AI 模型评测说明

本流程用于完成 M5 与 M7 的真实候选模型选型，不用于普通本地演示。调用模型可能产生费用，必须使用已获授权的图片，并在运行前确认供应商账户、预算和数据政策。

## 非计费服务能力预检

在上传图片或确认费用前，先运行只读模型列表预检：

```bash
uv run python manage.py probe_ai_service \
  --report docs/model-evaluations/service-capability-YYYY-MM-DD.json
```

命令只调用一次模型列表接口，不上传图片、不生成内容；未知供应商、未知模型或已有报告都会硬失败，避免凭模型名称猜测能力。2026-08-08 实跑只返回 `deepseek-v4-flash` 与 `deepseek-v4-pro`。DeepSeek 官方的[模型列表](https://api-docs.deepseek.com/api/list-models)与[集成说明](https://api-docs.deepseek.com/quick_start/agent_integrations/github_copilot/)确认 V4 为文本模型，图片场景需要其他视觉模型代理。因此当前服务不能完成 M5 图片分析或 M7 图像编辑评测，不能发送图片试错。

不可覆盖的实跑证据见 [`model-evaluations/service-capability-2026-08-08.json`](model-evaluations/service-capability-2026-08-08.json)。

## 硬性输入

- 每次只能评测 2～3 个唯一候选模型；
- 每个模型使用完全相同的 10～15 张 JPG/PNG；
- 图片应覆盖人物、宠物、物品、插画、透明背景、低分辨率、低对比、过暗、过亮和文字干扰；
- 必须使用 `--confirm-billable` 明确确认可能产生费用；
- `--run-id` 只能使用字母、数字、点、下划线、冒号和短横线；
- 已存在的报告不会被覆盖。

命令会先通过当前 OpenAI 兼容服务读取模型列表。任一候选不存在时立即终止，不执行图片分析或编辑调用。

## 图片分析

```bash
uv run python manage.py evaluate_ai_models \
  --capability analysis \
  --models gpt-5.6-luna gpt-5.6-terra gpt-5.6-sol \
  --image-dir evaluation-images \
  --output-dir docs/model-evaluations \
  --run-id analysis-2026-08 \
  --confirm-billable
```

报告自动记录 Schema 是否成功、延迟、主体、主体数量、适配结论和推荐参数。主体正确性、主体框、中文可读性及账单成本保持 `pending`，必须由人和供应商账单补充。

## 高级图像编辑

```bash
uv run python manage.py evaluate_ai_models \
  --capability advanced \
  --models gpt-image-2 another-compatible-image-model \
  --image-dir evaluation-images \
  --output-dir docs/model-evaluations \
  --run-id advanced-2026-08 \
  --advanced-operation style_transfer \
  --advanced-instruction '转换为清晰的拼豆插画风格' \
  --confirm-billable
```

每张成功结果独立保存，CSV 记录延迟、自动复查状态、主体相似度和变化比例。身份保留、指令符合度、安全性与真实成本仍须人工填写。单个模型或图片失败只记录异常类型并继续其他组合，异常消息、密钥和私有服务地址不会进入报告。

## 选型结论

评测完成后按同一标准比较首次成功率、主体正确性、低可靠表达、身份保留、局部编辑、中文说明、延迟、真实账单成本和安全性。只有人工字段全部完成后才能记录首选与降级模型；模拟模型不得参与真实供应商胜负结论。
