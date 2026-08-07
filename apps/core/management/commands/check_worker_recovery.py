from pathlib import Path
from uuid import uuid4

from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core.tasks import infrastructure_echo


class Command(BaseCommand):
    help = "Queue a task while workers are offline and wait for a restarted worker to finish it."

    def add_arguments(self, parser):
        parser.add_argument("--queued-signal", required=True)
        parser.add_argument("--timeout", type=float, default=30)

    def handle(self, *args, **options):
        timeout = options["timeout"]
        if connection.vendor != "postgresql":
            raise CommandError(f"Expected PostgreSQL, got {connection.vendor}.")
        if settings.CELERY_TASK_ALWAYS_EAGER:
            raise CommandError("Worker recovery requires CELERY_TASK_ALWAYS_EAGER=false.")
        if not 1 <= timeout <= 120:
            raise CommandError("Worker recovery timeout must be between 1 and 120 seconds.")

        expected = f"worker-recovery-{uuid4()}"
        result = infrastructure_echo.delay(expected)
        signal_path = Path(options["queued_signal"])
        try:
            signal_path.parent.mkdir(parents=True, exist_ok=True)
            with signal_path.open("x", encoding="utf-8") as signal:
                signal.write(f"{result.id}\n")
        except OSError as exc:
            raise CommandError(f"Cannot create queued signal: {exc}") from exc

        try:
            actual = result.get(timeout=timeout, disable_sync_subtasks=False)
        except CeleryTimeoutError as exc:
            raise CommandError("Restarted Celery worker did not finish the queued task.") from exc
        if actual != expected:
            raise CommandError("Restarted Celery worker returned an unexpected task result.")
        self.stdout.write(
            self.style.SUCCESS("Queued task completed after the Celery worker restart.")
        )
