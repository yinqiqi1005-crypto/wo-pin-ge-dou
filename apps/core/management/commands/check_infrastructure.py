from celery import __version__ as celery_version
from celery import group
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from redis import Redis

from apps.core.infrastructure_evidence import EvidenceWriteError, write_evidence
from apps.core.tasks import infrastructure_echo


class Command(BaseCommand):
    help = "Verify PostgreSQL, Redis and a real Celery worker end to end."

    def add_arguments(self, parser):
        parser.add_argument("--concurrent-tasks", type=int, default=4)
        parser.add_argument("--require-superuser", action="store_true")
        parser.add_argument("--report")

    def handle(self, *args, **options):
        concurrent_tasks = options.get("concurrent_tasks", 4)
        require_superuser = options.get("require_superuser", False)
        if not 2 <= concurrent_tasks <= 64:
            raise CommandError("Concurrent task count must be between 2 and 64.")
        if settings.CELERY_TASK_ALWAYS_EAGER:
            raise CommandError("Infrastructure check requires CELERY_TASK_ALWAYS_EAGER=false.")
        if connection.vendor != "postgresql":
            raise CommandError(f"Expected PostgreSQL, got {connection.vendor}.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                raise CommandError("PostgreSQL query check failed.")
            cursor.execute("SHOW server_version")
            postgres_version = cursor.fetchone()[0]

        redis = Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=5)
        if redis.ping() is not True:
            raise CommandError("Redis ping failed.")
        redis_version = redis.info(section="server").get("redis_version")
        if not redis_version:
            raise CommandError("Redis version check failed.")

        values = [f"worker-pong-{index}" for index in range(concurrent_tasks)]
        result = group(infrastructure_echo.s(value) for value in values).apply_async()
        if result.get(timeout=20) != values:
            raise CommandError("Concurrent Celery worker round trips failed.")

        active_superusers = (
            get_user_model()
            ._default_manager.filter(
                is_active=True,
                is_staff=True,
                is_superuser=True,
            )
            .count()
        )
        if require_superuser and active_superusers < 1:
            raise CommandError("An active superuser is required for this infrastructure check.")

        try:
            write_evidence(
                options.get("report"),
                {
                    "check": "target-infrastructure",
                    "database": {"engine": "postgresql", "version": postgres_version},
                    "redis": {"version": redis_version},
                    "celery": {
                        "always_eager": False,
                        "concurrent_round_trips": concurrent_tasks,
                        "version": celery_version,
                    },
                    "admin": {
                        "active_superuser_count": active_superusers,
                        "required": require_superuser,
                    },
                    "result": "passed",
                },
            )
        except EvidenceWriteError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("PostgreSQL, Redis and Celery are ready."))
