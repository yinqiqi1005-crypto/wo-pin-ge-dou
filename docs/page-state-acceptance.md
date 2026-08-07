# PRD 22 个页面状态验收映射

| # | 页面状态 | 可触发方式 | 自动化证据 |
|---:|---|---|---|
| 1 | 上传初始状态 | 进入 `/create/` | `test_upload_supports_accessible_click_drop_and_recent_task_recovery` |
| 2 | 上传进行中 | 选择文件并提交，表单进入 `aria-busy` 且按钮显示“正在上传” | 浏览器流程及上传模板断言 |
| 3 | 上传失败 | 上传损坏、非图片或超过 10MB | `test_upload_rejects_non_image_file`、`test_oversized_but_decodable_image_is_rejected_without_task` |
| 4 | 分析进行中 | 任务为 `uploaded/analyzing` | 分析模板状态分支与任务状态测试 |
| 5 | 分析完成且适合 | `suitability=suitable` | `test_analysis_renders_all_four_suitability_states_in_plain_language` |
| 6 | 主体不确定 | 低置信结果并显示重选区域 | `test_uncertain_subject_can_be_reselected_without_another_model_call` |
| 7 | 图片风险较高 | `try/not_suitable` 且最多三个问题 | 六步体验测试与结构化 Schema 测试 |
| 8 | 无法处理 | `unprocessable` 或分析最终失败 | 四状态测试与分析降级测试 |
| 9 | 确认基础设置 | 分析后进入设置页 | 基础闭环与 Playwright 流程 |
| 10 | 确认高级设置 | Plus/Pro 从版本进入高级创作 | `test_plus_content_creation_adds_child_version_and_consumes_one` |
| 11 | 会员权限不足 | 注册会员进入高级创作或基础功能被后台关闭 | 会员权限测试与任务快照权限测试 |
| 12 | 剩余张数不足 | 周期剩余为 0 后提交 | 游客第二次生成与张数错误保留设置测试 |
| 13 | 排队中 | `status=queued` | 进度页五阶段测试和取消测试 |
| 14 | 生成中 | `status=generating` | 后台状态机与持久阶段测试 |
| 15 | 自动重试中 | 首次处理失败 | `test_first_generation_failure_then_automatic_retry_succeeds_without_second_reservation` |
| 16 | 生成失败 | 两次处理均失败 | 失败释放张数测试 |
| 17 | 图纸预览 | 任务成功进入结果页 | 基础闭环、结果三标签和 Playwright 鼠标/键盘测试 |
| 18 | 参数调整 | 从任意旧版本进入免费调整 | `test_parameter_adjustment_reuses_base_and_does_not_use_quota` |
| 19 | 内容型二次创作 | Plus/Pro 高级创作 | 高级创作父子版本测试 |
| 20 | 保存中 | 保存提交后表单进入 `aria-busy` 且按钮显示“正在保存” | 浏览器流程及保存模板断言 |
| 21 | 保存成功 | 保存后进入所属图纸详情 | 基础闭环、游客注册接续和 Playwright 测试 |
| 22 | 保存失败 | 数据库保存异常，保留生成结果 | `test_save_database_failure_preserves_generated_result_for_retry` |

所有状态必须有文字或结构语义，不能只依赖颜色。页面错误靠近对应表单；排队、生成和保存状态刷新后仍由数据库恢复。

## 响应式和键盘验收

- Chromium 分别在 1280px 桌面和 390px 手机视口完成登录、上传、分析、设置、生成、三结果标签、保存和图纸库流程；
- 手机视口必须保留“AI 创作/我的图纸”主导航，首页、结果和图纸详情不得横向溢出；
- 纯键盘 Chromium 路径先验证“跳到主要内容”，再使用焦点 + Enter 激活主要按钮和链接；
- 结果页由 JavaScript 增强为 `tablist/tab/tabpanel`，支持左右方向键和 Home/End；JavaScript 不可用时，三个结果区仍全部出现在服务器 HTML 中。

## 异常端到端验收

| 开发计划场景 | Chromium 证据 |
|---|---|
| 上传损坏文件 | `test_browser_rejects_damaged_upload_next_to_the_file_control` |
| 主体不确定后重新选择 | `test_browser_reselects_an_uncertain_subject_without_reuploading` |
| 剩余张数不足且保留设置 | `test_browser_keeps_settings_when_generation_images_are_exhausted` |
| 首次生成失败、免费自动重试成功 | `test_browser_explains_free_retry_and_recovers_from_save_failure` |
| 保存失败不破坏结果，再次保存成功 | `test_browser_explains_free_retry_and_recovers_from_save_failure` |
| 生成最终失败且释放预留张数 | `test_browser_shows_final_generation_failure_and_releases_reserved_image` |

浏览器测试同时查数据库中的任务状态、重试次数、预留/使用流水和剩余张数，不只判断页面是否出现某段文字。

## 第一次真人可用性走查

M6 完成门槛要求一名项目开发之外的真人测试者依次完成以下六个固定任务：

1. 上传图片并理解质量反馈；
2. 确认或重新选择主体；
3. 选择尺寸/颜色并理解本次张数；
4. 等待生成并能从任务状态恢复；
5. 查看效果、编号网格和材料清单；
6. 保存作品并在“我的图纸”中重新找到。

使用匿名代号填写 [`usability-walkthrough.csv`](usability-walkthrough.csv)，不要记录姓名、联系方式或其他个人信息。每个任务必须记录完成状态、协助次数、用时、困惑严重度和观察；项目成员只可担任记录人，不能代替外部测试者。存在 `pending`、任务缺失/重复、未完成任务、重大/严重困惑、无观察记录或超过 90 天的记录时，以下命令会失败：

```bash
uv run python manage.py check_usability_walkthrough \
  --results docs/usability-walkthrough.csv \
  --report docs/usability-walkthroughs/session-YYYY-MM-DD.json
```

报告采用排他创建，不能覆盖旧证据。走查发现的问题必须进入 `docs/issues.csv`；不能为了让命令通过而把未完成任务写成已完成。
