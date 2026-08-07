# 实体拼豆制作验证

这一步用于完成 M9-18，必须由真人使用实体拼豆、模板和熨斗完成。自动化测试只能检查证据格式，不能替代制作行为。

## 固定样例

从 `media/human-review/round-3/` 选择以下三张 30×30 编号网格：

1. `grids/per-01.png`：人物；
2. `grids/pet-01.png`：宠物；
3. `grids/obj-01.png`：物品。

三张图的计划用豆量均为 900 颗，来源是正式网格材料统计，不是人工估算。

## 每张作品必须记录

- `actual_beads`：实际使用豆数，必须大于 0；
- `bead_difference`：必须等于实际豆数减计划豆数，可以为负数；
- `color_substitutions`：缺色和替代色，没有则填写“无”；
- `making_minutes`：从放豆到熨烫完成的总分钟数；
- `ironing_result`：只有成品结构稳定时填写 `pass`，失败必须保留为 `fail`；
- `finished_photo`：CSV 所在目录内的 JPG/PNG 相对路径；
- `reviewer` 与 `review_date`：真实评审人和不晚于今天的 ISO 日期；
- `status`：所有证据完成后才改为 `complete`；
- `notes`：记录断裂、错位、补豆、色差或重新熨烫情况。

建议把照片保存为：

```text
docs/physical-validation-photos/per-01.png
docs/physical-validation-photos/pet-01.png
docs/physical-validation-photos/obj-01.png
```

CSV 中对应写 `physical-validation-photos/per-01.png` 等相对路径。照片不要包含不必要的人脸、住址或其他个人信息。

## 验收

填写 `docs/physical-validation.csv` 后运行完整发布门槛：

```bash
uv run python manage.py check_release_quality \
  --results docs/test-results-40.csv \
  --physical-results docs/physical-validation.csv \
  --issues docs/issues.csv \
  --deployment-report docs/deployment-smoke/production-2026-08.json
```

生成尝试、自动重试、张数扣减和未完成任务会从当前数据库自动计算，不需要也不允许手填。缺少类别、不是 30×30、记录未完成、数量差值错误、制作时长无效、熨烫失败、图片缺失/损坏、评审人或日期缺失都会失败。不要为了通过命令修改这些标准。
