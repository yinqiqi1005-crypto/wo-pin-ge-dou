from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.core.management.base import CommandError

from apps.core.management.commands.check_infrastructure import Command


class FakeCursor:
    def execute(self, statement):
        assert statement == "SELECT 1"

    def fetchone(self):
        return (1,)


def test_infrastructure_command_checks_four_concurrent_worker_round_trips():
    command = Command()
    redis = Mock()
    redis.ping.return_value = True
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
