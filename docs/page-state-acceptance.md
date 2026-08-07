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
| 17 | 图纸预览 | 任务成功进入结果页 | 基础闭环、结果三标签和 Playwright 测试 |
| 18 | 参数调整 | 从任意旧版本进入免费调整 | `test_parameter_adjustment_reuses_base_and_does_not_use_quota` |
| 19 | 内容型二次创作 | Plus/Pro 高级创作 | 高级创作父子版本测试 |
| 20 | 保存中 | 保存提交后表单进入 `aria-busy` 且按钮显示“正在保存” | 浏览器流程及保存模板断言 |
| 21 | 保存成功 | 保存后进入所属图纸详情 | 基础闭环、游客注册接续和 Playwright 测试 |
| 22 | 保存失败 | 数据库保存异常，保留生成结果 | `test_save_database_failure_preserves_generated_result_for_retry` |

所有状态必须有文字或结构语义，不能只依赖颜色。页面错误靠近对应表单；排队、生成和保存状态刷新后仍由数据库恢复。
