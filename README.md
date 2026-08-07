# 我拼个豆（AI Bead Pattern Creator）

面向求职作品集的消费级 AI 拼豆创作产品 Demo。用户上传人物、宠物、物品或插画后，可以完成图片分析、主体确认、参数推荐、图纸生成、材料统计、版本创作以及 PNG/PDF 导出。产品不接真实支付，会员和张数均为可配置模拟业务。

## 已实现能力

- JPG/PNG 上传、质量与主体分析、规则降级和可配置真实多模态适配器；
- 30×30、50×50、70×70 正式网格，12/24/36 色，透明格、色板映射和孤立格清理；
- 免费游客、注册、Plus、Pro 配置，按张数预留、使用、释放和审计；
- Celery 后台任务、有限重试、取消、失败恢复和持久进度；
- Plus/Pro 风格、背景、轮廓、元素和局部创作，父子版本和视觉复查；
- 图纸库、版本历史、软删除、效果 PNG、编号 PNG 和分页制作 PDF；
- Django Admin 运营配置、模型调用、任务、张数和配置版本审计；
- 单元、集成、并发、40 图回归、PDF 像素渲染和 Playwright 浏览器测试。

## 架构原则

AI 负责理解图片和创作底图，确定性算法负责最终网格、合法色号、预览和材料数量。`PatternVersion.grid_data` 是正式图纸唯一数据源。供应商、会员和运营配置不会散落在页面代码中；任务创建时保存配置快照。

详见 [架构说明](docs/architecture.md)、[PRD](prd.md)、[开发计划](development-plan.md) 和 [测试报告](docs/test-report.md)。

## 最小本地启动（SQLite + 同步任务）

需要 Python 3.12 和 uv。

```bash
uv sync --dev
cp .env.example .env
uv run python manage.py migrate
uv run python manage.py seed_demo_config
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

打开 <http://127.0.0.1:8000/>。本地默认使用 SQLite 和 Celery eager，适合学习与页面演示；这不等同于正式队列并发验收。

## PostgreSQL + Redis + Celery 演示环境

先在 `.env` 设置随机的 `DJANGO_SECRET_KEY` 和 `DB_PASSWORD`，再运行：

```bash
docker compose up -d postgres redis
DB_ENGINE=postgresql uv run python manage.py migrate
CELERY_TASK_ALWAYS_EAGER=false uv run celery -A config worker -l info
DB_ENGINE=postgresql CELERY_TASK_ALWAYS_EAGER=false uv run python manage.py runserver
```

也可以构建容器化 Web 与 Worker。首次启动 Web 前执行迁移：

```bash
docker compose run --rm web uv run python manage.py migrate
docker compose up --build web worker
```

## 演示账号与素材

不会在仓库硬编码演示密码。先设置后台配置，再显式提供至少 12 位的临时密码：

```bash
uv run python manage.py seed_demo_config
uv run python manage.py prepare_demo --password 'your-temporary-demo-password'
```

命令创建注册、Plus、Pro 三个账号；免费游客直接未登录访问。三张稳定素材写入 `media/demo-assets/`。完整演示路径见 [演示手册](docs/demo-runbook.md)。

## 质量检查

```bash
uv run ruff check .
uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
uv run pytest
```

浏览器测试需要 Chromium：

```bash
uv run playwright install chromium
uv run pytest tests/e2e -q
```

CI 会安装 Poppler 和 Noto CJK 字体，实际渲染三种尺寸的 PDF 后再验收。健康检查位于 `/health/`。

## M9 发布质量门槛

`docs/test-results-40.csv` 将自动化技术结果与真人观察结果分栏保存。真人完成 40 图评审、至少 3 个高级创作案例、生产环境冒烟和运营指标统计后运行：

```bash
uv run python manage.py check_release_quality \
  --generation-attempts 100 \
  --automatic-retries 10 \
  --wrong-charges 0 \
  --open-critical-issues 0 \
  --deployment-smoke passed
```

存在任何 `pending`、材料不一致、主体可辨认率低于 85%、严重主体错误率达到 5%、可制作率低于 85%、高级创作符合率低于 85%、自动重试率达到 15%、错误扣减、P0/P1 问题或部署冒烟失败时，命令都会失败。示例数字仅展示命令格式，正式发布必须填入真实统计值。

## 真实模型配置

默认 `rules` 分析和 `mock` 高级创作保证离线可演示。配置真实 OpenAI 兼容服务时，把密钥放入环境变量，并在 Admin 新建模型路由版本。模型失败只记录错误类型；日志和数据库不保存密钥。

## 安全与商业边界

- 不接真实支付，不保存支付资料；
- 上传和作品只对所属用户可见；
- 删除采用软删除和延迟资源清理；
- 生产环境必须启用 HTTPS、安全 Cookie、随机密钥、对象存储和外部监控；
- 仓库中的会员张数和模型名称都是可修改 Demo 默认值，不是最终商业承诺。
