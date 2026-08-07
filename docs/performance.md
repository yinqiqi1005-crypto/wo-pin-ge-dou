# 发布性能基线

M9-20 使用固定输入和固定上限检查本地可确定链路，避免只凭主观体感宣称“性能良好”。

## 执行方式

```bash
uv run python manage.py check_release_performance \
  --iterations 3 \
  --report docs/performance/local-YYYY-MM-DD.json
```

报告采用排他创建，已存在的路径不会被覆盖。每次正式验收应使用新文件名，保留历史变化。

## 固定检查

| 阶段 | 真实执行内容 | 单次上限 |
|---|---|---:|
| `upload_storage` | 800×600 PNG 通过当前 Django 存储写入、读回和字节一致性校验 | 2 秒 |
| `rule_analysis` | 本地规则分析适配器完整运行并返回主体 | 2 秒 |
| `pattern_generation` | 最大 70×70、36 色正式转换，并渲染效果 PNG 和编号网格 PNG | 10 秒 |
| `pdf_export` | 从同一份正式网格生成完整分页 PDF | 10 秒 |

每个阶段记录全部样本、中位数和最大值；任一样本超过固定上限时命令立即失败，不通过四舍五入掩盖超限。

## 证据边界

这份基线验证确定性图片处理、存储和导出链路，不代表真实 AI 供应商或公网的延迟。真实模型延迟和成本必须由 `evaluate_ai_models` 在同一组 10～15 张图片上记录；公网可用性必须由 `smoke_deployment` 独立验证。

2026-08-08 本机三次迭代证据保存在 [`performance/local-2026-08-08.json`](performance/local-2026-08-08.json)。
