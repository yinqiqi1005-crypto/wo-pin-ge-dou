# 我拼个豆

AI Bead Pattern Creator：将用户图片转换为可实际制作的拼豆图纸。

## Local development

1. Create the project environment:

   ```bash
   uv sync --dev
   ```

2. Copy `.env.example` to `.env` and update local values.

3. Apply database migrations:

   ```bash
   uv run python manage.py migrate
   ```

4. Start the web application:

   ```bash
   uv run python manage.py runserver
   ```

5. In a separate terminal, start the task worker after Redis is available:

   ```bash
   uv run celery -A config worker -l info
   ```

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The health endpoint is available at `/health/`.

