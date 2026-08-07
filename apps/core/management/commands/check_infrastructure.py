from celery import group
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from redis import Redis

from apps.core.tasks import infrastructure_echo


class Command(BaseCommand):
    help = "Verify PostgreSQL, Redis and a real Celery worker end to end."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError(f"Expected PostgreSQL, got {connection.vendor}.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                raise CommandError("PostgreSQL query check failed.")

        redis = Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=5)
        if redis.ping() is not True:
            raise CommandError("Redis ping failed.")

        values = [f"worker-pong-{index}" for index in range(4)]
        result = group(infrastructure_echo.s(value) for value in values).apply_async()
        if result.get(timeout=20) != values:
            raise CommandError("Concurrent Celery worker round trips failed.")
        self.stdout.write(self.style.SUCCESS("PostgreSQL, Redis and Celery are ready."))
