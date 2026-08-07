# 作品集 Demo 交付说明

## 当前结论

“我拼个豆”已经达到可运行、可讲解、可录屏的求职作品集 Demo 标准。作品集模式默认使用本地规则分析和确定性高级创作适配器，不依赖付费模型、真实支付、公网域名、外部测试者或实体拼豆。

这不是缩减产品功能：上传、分析、主体确认、尺寸与颜色设置、后台任务、按张数结算、效果图、编号网格、材料清单、保存、图纸库、Plus/Pro 二次创作、版本历史、PNG/PDF 导出和运营后台均使用正式业务代码。被暂缓的是外部商业验证，不是产品主流程。

2026-08-08 的本地就绪检查已经通过，证据见 [`portfolio-readiness/local-2026-08-08.json`](portfolio-readiness/local-2026-08-08.json)。检查内容包括：

- 首页、登录页和健康检查真实返回 200；
- 免费游客、注册会员、Plus、Pro 四档配置完整；
- 注册、Plus、Pro 三个演示账号可用且会员层级正确；
- 三张演示素材均可解码，并能生成合法 30×30、最多 12 色的正式图纸；
- 图片分析固定走 `rules`，高级创作固定走 `mock`，离线演示不会因外部 API 失效；
- 生产环境验证明确记录为 `not_evaluated`，不会被误写成已完成。

## 一次性准备

```bash
uv sync --dev
uv run python manage.py migrate
uv run python manage.py seed_demo_config
uv run python manage.py prepare_demo --password '至少12位的临时演示密码'
uv run python manage.py check_portfolio_demo
uv run python manage.py runserver
```

打开 <http://127.0.0.1:8000/>。免费游客直接点击“开始创作”；需要展示会员差异时，登录 `demo_registered`、`demo_plus` 或 `demo_pro`。演示密码由运行 `prepare_demo` 的人临时指定，不写入仓库。

## 推荐的 7 分钟面试演示

1. 首页讲清“按张数而非点数”和“AI 理解、算法保证可制作”；
2. 用游客上传人物素材，展示质量分析、主体建议和剩余 1 张；
3. 选择 30×30、12 色生成，切换效果图、编号网格和材料建议；
4. 保存后进入图纸库，打开版本详情并导出 PNG/PDF；
5. 登录 `demo_plus`，展示风格转换与父子版本，说明高级创作消耗 1 张；
6. 展示免费参数调整不会再次消耗张数；
7. 打开 Django Admin，展示会员配置、模型路由、任务状态、调用日志和张数流水。

仓库也保存了真实 Chromium 主流程录像 [`demo-recordings/basic-flow.webm`](demo-recordings/basic-flow.webm)，可在面试现场环境异常时备用。

## 求职表达边界

可以表达：

- “完成了可运行的消费级 AI 拼豆产品 Demo”；
- “实现了可替换的多模态模型适配层，作品集环境使用离线适配器保证稳定演示”；
- “使用 262 项自动测试、真实浏览器、PostgreSQL、Redis、Celery 和 GitHub Actions 验证工程质量”；
- “为真人评审、实体制作和公网发布设计了严格证据门槛”。

暂时不要表达：

- “已经经过真实用户研究并证明转化效果”；
- “真实多模态模型已经完成成本和质量选型”；
- “实体拼豆可制作率已经由真人验证”；
- “产品已经在公网生产环境运营”。

这些项目属于未来商业验证，不影响作品集 Demo 运行和展示。
