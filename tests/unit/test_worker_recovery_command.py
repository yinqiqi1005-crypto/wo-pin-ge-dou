import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.core.management.base import CommandError

from apps.core.management.commands.check_worker_recovery import Command

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def command_dependencies(*, vendor="postgresql", eager=False):
    return (
        patch(
            "apps.core.management.commands.check_worker_recovery.connection",
            SimpleNamespace(vendor=vendor),
        ),
        patch(
            "apps.core.management.commands.check_worker_recovery.settings",
            SimpleNamespace(CELERY_TASK_ALWAYS_EAGER=eager),
        ),
    )


def test_worker_recovery_queues_before_signalling_and_waits_for_same_result(tmp_path):
    signal_path = tmp_path / "worker-recovery.queued"
    result = Mock(id="task-result-id")
    queued_value = {}

    def queue(value):
        queued_value["value"] = value
        return result

    def finish(*, timeout, disable_sync_subtasks):
        assert timeout == 30
        assert disable_sync_subtasks is False
        assert signal_path.read_text(encoding="utf-8") == "task-result-id\n"
        return queued_value["value"]

    result.get.side_effect = finish
    database, celery_settings = command_dependencies()
    with (
        database,
        celery_settings,
        patch(
            "apps.core.management.commands.check_worker_recovery.infrastructure_echo.delay",
            side_effect=queue,
        ) as delay,
    ):
        Command().handle(queued_signal=signal_path, timeout=30)

    delay.assert_called_once()
    assert queued_value["value"].startswith("worker-recovery-")


def test_worker_recovery_writes_non_overwritable_evidence(tmp_path):
    signal_path = tmp_path / "worker-recovery.queued"
    report_path = tmp_path / "worker-recovery.json"
    result = Mock(id="task-result-id")
    queued_value = {}

    def queue(value):
        queued_value["value"] = value
        return result

    result.get.side_effect = lambda **_kwargs: queued_value["value"]
    database, celery_settings = command_dependencies()
    with (
        database,
        celery_settings,
        patch(
            "apps.core.management.commands.check_worker_recovery.infrastructure_echo.delay",
            side_effect=queue,
        ),
    ):
        Command().handle(
            queued_signal=signal_path,
            timeout=30,
            report=str(report_path),
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "passed"
    assert report["task_id"] == "task-result-id"
    assert report["celery"]["queued_while_worker_offline"] is True
    assert report["celery"]["same_task_result_verified"] is True

    second_signal = tmp_path / "second.queued"
    database, celery_settings = command_dependencies()
    with (
        database,
        celery_settings,
        patch(
            "apps.core.management.commands.check_worker_recovery.infrastructure_echo.delay",
            side_effect=queue,
        ),
        pytest.raises(CommandError, match="Cannot create infrastructure evidence"),
    ):
        Command().handle(
            queued_signal=second_signal,
            timeout=30,
            report=str(report_path),
        )


@pytest.mark.parametrize(
    ("vendor", "eager", "message"),
    [
        ("sqlite", False, "Expected PostgreSQL"),
        ("postgresql", True, "CELERY_TASK_ALWAYS_EAGER=false"),
    ],
)
def test_worker_recovery_rejects_non_production_infrastructure(
    tmp_path,
    vendor,
    eager,
    message,
):
    database, celery_settings = command_dependencies(vendor=vendor, eager=eager)
    with database, celery_settings, pytest.raises(CommandError, match=message):
        Command().handle(queued_signal=tmp_path / "signal", timeout=30)


def test_worker_recovery_rejects_timeout_without_weakening_the_gate(tmp_path):
    result = Mock(id="task-result-id")
    result.get.side_effect = CeleryTimeoutError()
    database, celery_settings = command_dependencies()
    with (
        database,
        celery_settings,
        patch(
            "apps.core.management.commands.check_worker_recovery.infrastructure_echo.delay",
            return_value=result,
        ),
        pytest.raises(CommandError, match="did not finish"),
    ):
        Command().handle(queued_signal=tmp_path / "signal", timeout=30)


def test_worker_recovery_signal_cannot_overwrite_previous_evidence(tmp_path):
    signal_path = tmp_path / "signal"
    signal_path.write_text("previous-task\n", encoding="utf-8")
    database, celery_settings = command_dependencies()
    with (
        database,
        celery_settings,
        patch(
            "apps.core.management.commands.check_worker_recovery.infrastructure_echo.delay",
            return_value=Mock(id="new-task"),
        ),
        pytest.raises(CommandError, match="Cannot create queued signal"),
    ):
        Command().handle(queued_signal=signal_path, timeout=30)

    assert signal_path.read_text(encoding="utf-8") == "previous-task\n"


@pytest.mark.parametrize("timeout", [0, 121])
def test_worker_recovery_timeout_has_fixed_safe_bounds(tmp_path, timeout):
    database, celery_settings = command_dependencies()
    with database, celery_settings, pytest.raises(CommandError, match="between 1 and 120"):
        Command().handle(queued_signal=tmp_path / "signal", timeout=timeout)


def test_ci_stops_first_worker_and_queues_before_starting_replacement():
    workflow = (PROJECT_ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    recovery_block = workflow.split("- name: Verify queued task survives worker restart", 1)[1]

    stop_position = recovery_block.index('kill "$first_worker_pid"')
    queue_position = recovery_block.index("check_worker_recovery")
    queued_signal_position = recovery_block.index("wo-pin-ge-dou-worker-recovery.queued")
    replacement_position = recovery_block.index(
        "uv run celery -A config worker",
        queue_position,
    )

    assert stop_position < queue_position < queued_signal_position < replacement_position
    assert 'CELERY_TASK_ALWAYS_EAGER: "false"' in workflow
    assert workflow.count("--concurrent-tasks 10") == 2
    assert "--report artifacts/worker-recovery.json" in workflow
    assert workflow.count("actions/checkout@v7") == 2
    assert workflow.count("astral-sh/setup-uv@v9") == 2
    assert workflow.count("prune-cache: true") == 2
    assert "actions/upload-artifact@v7" in workflow
    assert "path: artifacts/*.json" in workflow
