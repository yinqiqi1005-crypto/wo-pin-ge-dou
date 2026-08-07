import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.core.management.base import CommandError

from apps.core.management.commands.check_infrastructure import Command


class FakeCursor:
    def __init__(self):
        self.statement = None

    def execute(self, statement):
        assert statement in {"SELECT 1", "SHOW server_version"}
        self.statement = statement

    def fetchone(self):
        if self.statement == "SELECT 1":
            return (1,)
        return ("16.6",)


def command_settings():
    return patch(
        "apps.core.management.commands.check_infrastructure.settings",
        SimpleNamespace(
            CELERY_BROKER_URL="redis://example.invalid/0",
            CELERY_TASK_ALWAYS_EAGER=False,
        ),
    )


def user_model(superuser_count=1):
    manager = Mock()
    manager.filter.return_value.count.return_value = superuser_count
    return patch(
        "apps.core.management.commands.check_infrastructure.get_user_model",
        return_value=SimpleNamespace(_default_manager=manager),
    )


def test_infrastructure_command_checks_four_concurrent_worker_round_trips():
    command = Command()
    redis = Mock()
    redis.ping.return_value = True
    redis.info.return_value = {"redis_version": "7.2.7"}
    result = Mock()
    result.get.return_value = [f"worker-pong-{index}" for index in range(4)]
    task_group = Mock()
    task_group.apply_async.return_value = result
    captured_signatures = []

    def build_group(signatures):
        captured_signatures.extend(signatures)
        return task_group

    database = SimpleNamespace(
        vendor="postgresql",
        cursor=lambda: nullcontext(FakeCursor()),
    )

    with (
        patch(
            "apps.core.management.commands.check_infrastructure.connection",
            database,
        ),
        command_settings(),
        user_model(),
        patch(
            "apps.core.management.commands.check_infrastructure.Redis.from_url",
            return_value=redis,
        ),
        patch(
            "apps.core.management.commands.check_infrastructure.infrastructure_echo.s",
            side_effect=lambda value: value,
        ),
        patch(
            "apps.core.management.commands.check_infrastructure.group",
            side_effect=build_group,
        ),
    ):
        command.handle()

    assert captured_signatures == [f"worker-pong-{index}" for index in range(4)]
    result.get.assert_called_once_with(timeout=20)


def test_infrastructure_command_fails_if_worker_results_are_incomplete():
    command = Command()
    redis = Mock()
    redis.ping.return_value = True
    redis.info.return_value = {"redis_version": "7.2.7"}
    result = Mock()
    result.get.return_value = ["worker-pong-0"]
    task_group = Mock()
    task_group.apply_async.return_value = result

    def build_group(signatures):
        list(signatures)
        return task_group

    database = SimpleNamespace(
        vendor="postgresql",
        cursor=lambda: nullcontext(FakeCursor()),
    )

    with (
        patch(
            "apps.core.management.commands.check_infrastructure.connection",
            database,
        ),
        command_settings(),
        user_model(),
        patch(
            "apps.core.management.commands.check_infrastructure.Redis.from_url",
            return_value=redis,
        ),
        patch(
            "apps.core.management.commands.check_infrastructure.infrastructure_echo.s",
            side_effect=lambda value: value,
        ),
        patch(
            "apps.core.management.commands.check_infrastructure.group",
            side_effect=build_group,
        ),
        pytest.raises(CommandError, match="Concurrent Celery worker round trips failed"),
    ):
        command.handle()


def test_infrastructure_command_writes_non_overwritable_real_service_evidence(tmp_path):
    report_path = tmp_path / "infrastructure.json"
    redis = Mock()
    redis.ping.return_value = True
    redis.info.return_value = {"redis_version": "7.2.7"}
    result = Mock()
    result.get.return_value = [f"worker-pong-{index}" for index in range(10)]
    task_group = Mock()
    task_group.apply_async.return_value = result
    database = SimpleNamespace(
        vendor="postgresql",
        cursor=lambda: nullcontext(FakeCursor()),
    )

    with (
        patch("apps.core.management.commands.check_infrastructure.connection", database),
        command_settings(),
        user_model(),
        patch(
            "apps.core.management.commands.check_infrastructure.Redis.from_url",
            return_value=redis,
        ),
        patch(
            "apps.core.management.commands.check_infrastructure.infrastructure_echo.s",
            side_effect=lambda value: value,
        ),
        patch(
            "apps.core.management.commands.check_infrastructure.group",
            return_value=task_group,
        ),
    ):
        Command().handle(
            concurrent_tasks=10,
            require_superuser=True,
            report=str(report_path),
        )

        with pytest.raises(CommandError, match="Cannot create infrastructure evidence"):
            Command().handle(
                concurrent_tasks=10,
                require_superuser=True,
                report=str(report_path),
            )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "passed"
    assert report["database"] == {"engine": "postgresql", "version": "16.6"}
    assert report["redis"] == {"version": "7.2.7"}
    assert report["celery"]["always_eager"] is False
    assert report["celery"]["concurrent_round_trips"] == 10
    assert report["admin"] == {"active_superuser_count": 1, "required": True}


@pytest.mark.parametrize("concurrent_tasks", [1, 65])
def test_infrastructure_command_rejects_weak_or_unsafe_concurrency(concurrent_tasks):
    with pytest.raises(CommandError, match="between 2 and 64"):
        Command().handle(concurrent_tasks=concurrent_tasks)


def test_infrastructure_command_rejects_eager_mode():
    with (
        patch(
            "apps.core.management.commands.check_infrastructure.settings",
            SimpleNamespace(CELERY_TASK_ALWAYS_EAGER=True),
        ),
        pytest.raises(CommandError, match="CELERY_TASK_ALWAYS_EAGER=false"),
    ):
        Command().handle()
