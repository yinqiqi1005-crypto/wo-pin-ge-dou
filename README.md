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

公网部署完成后，用真实 HTTPS 域名运行并保存不可覆盖的验收证据：

```bash
uv run python manage.py smoke_deployment \
  --base-url https://demo.example.com \
  --expected-host demo.example.com \
  --report docs/deployment-smoke/production-2026-08.json
```

命令检查健康页、产品首页、指纹 CSS/JavaScript、HTTPS 最终地址、目标域名，以及 HSTS、点击劫持、MIME 嗅探和 Referrer Policy 响应头。`--allow-http-localhost` 只用于本机生产进程冒烟，不能作为公网发布证据。

确定性性能基线使用最大 70×70/36 色输出，实际测量存储读回、规则分析、图纸/PNG 生成和完整 PDF 导出：

```bash
uv run python manage.py check_release_performance \
  --iterations 3 \
  --report docs/performance/local-YYYY-MM-DD.json
```

固定上限、报告字段和证据边界见 [性能基线说明](docs/performance.md)。

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

`docs/test-results-40.csv` 将自动化技术结果与真人观察结果分栏保存。真人完成 40 图评审、至少 3 个高级创作案例、生产环境冒烟和问题登记后运行：

```bash
uv run python manage.py check_release_quality \
  --physical-results docs/physical-validation.csv \
  --issues docs/issues.csv \
  --deployment-report docs/deployment-smoke/production-2026-08.json
```

命令会直接从数据库的生成任务和张数流水计算尝试数、重试率、错误扣减与未完成任务；从 `docs/issues.csv` 读取 P0/P1；并校验 7 天内的真实 HTTPS 部署报告。这些值不再允许由发布人手填。存在任何 `pending`、材料不一致、主体可辨认率低于 85%、严重主体错误率达到 5%、可制作率低于 85%、高级创作符合率低于 85%、三类实体制作证据不完整、自动重试率达到 15%、错误扣减、未完成生成、P0/P1 问题或部署证据失效时，命令都会失败。实体制作步骤见 [实物验证说明](docs/physical-validation.md)。

开始真人评分前生成不可覆盖的 40 图对照包：

```bash
uv run python manage.py prepare_human_review \
  --output-dir media/human-review/round-1 \
  --results docs/test-results-40.csv
```

打开输出目录的 `index.html`，逐图比较原图、拼豆效果与高分辨率编号网格，直接选择四类人工结论并填写备注。页面会尝试在本机浏览器保存进度，也可随时下载进度 CSV；40 图全部完成前，“下载最终 CSV”保持禁用。评审包会保存 120 张图片、技术参数、材料统计和 SHA-256 清单，不加载任何网络资源；再次运行必须使用新的轮次目录，不能覆盖旧证据。

## 真实模型配置

默认 `rules` 分析和 `mock` 高级创作保证离线可演示。配置真实 OpenAI 兼容服务时，把密钥放入环境变量，并在 Admin 新建模型路由版本。模型失败只记录错误类型；日志和数据库不保存密钥。

真实候选模型评测必须使用 2～3 个模型和同一目录下 10～15 张已获授权的 JPG/PNG，并显式确认可能产生 API 费用：

```bash
uv run python manage.py evaluate_ai_models \
  --capability analysis \
  --models gpt-5.6-luna gpt-5.6-terra \
  --image-dir evaluation-images \
  --output-dir docs/model-evaluations \
  --run-id analysis-2026-08 \
  --confirm-billable
```

高级图像编辑把 `--capability` 改为 `advanced`，并选择服务实际提供的图像编辑模型。命令会先查询当前服务模型列表；模型不存在时在任何付费调用前失败。完整字段和人工评分步骤见 [模型评测说明](docs/model-evaluation.md)。

## 安全与商业边界

- 不接真实支付，不保存支付资料；
- 上传和作品只对所属用户可见；
- 删除采用软删除和延迟资源清理；
- 生产环境必须启用 HTTPS、安全 Cookie、随机密钥、对象存储和外部监控；
- 仓库中的会员张数和模型名称都是可修改 Demo 默认值，不是最终商业承诺。
