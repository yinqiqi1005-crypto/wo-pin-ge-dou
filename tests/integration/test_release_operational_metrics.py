from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.creation.models import GenerationStatus, GenerationTask
from apps.memberships.models import (
    GenerationQuotaLedger,
    GenerationQuotaPeriod,
    MembershipLevel,
    MembershipPlan,
    QuotaLedgerEvent,
    QuotaPeriodType,
)
from apps.operations.release_evidence import collect_operational_metrics

pytestmark = pytest.mark.django_db


def create_quota(django_user_model, *, used_count=0, reserved_count=0):
    user = django_user_model.objects.create_user(username=f"release-user-{uuid4()}")
    plan = MembershipPlan.objects.create(
        level=MembershipLevel.REGISTERED,
        name="Registered",
        quota_period=QuotaPeriodType.MONTHLY,
        generation_limit=20,
    )
    quota = GenerationQuotaPeriod.objects.create(
        user=user,
        plan=plan,
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(days=30),
        total_limit=20,
        used_count=used_count,
        reserved_count=reserved_count,
    )
    return user, quota


def create_task(user, quota, *, status, retry_count=0, started=True):
    return GenerationTask.objects.create(
        user=user,
        quota_period=quota,
        status=status,
        idempotency_key=f"task-{uuid4()}",
        started_at=timezone.now() if started else None,
        retry_count=retry_count,
    )


def add_event(quota, task_reference, event, *, amount=1):
    return GenerationQuotaLedger.objects.create(
        quota_period=quota,
        task_reference=task_reference,
        event=event,
        amount=amount,
        idempotency_key=f"ledger-{uuid4()}",
    )


def test_operational_metrics_derive_attempts_retries_and_charges(django_user_model):
    user, quota = create_quota(django_user_model, used_count=1)
    succeeded = create_task(user, quota, status=GenerationStatus.SUCCEEDED)
    failed = create_task(
        user,
        quota,
        status=GenerationStatus.FAILED,
        retry_count=1,
    )
    add_event(quota, succeeded.id, QuotaLedgerEvent.RESERVE)
    add_event(quota, succeeded.id, QuotaLedgerEvent.CONSUME)
    add_event(quota, failed.id, QuotaLedgerEvent.RESERVE)
    add_event(quota, failed.id, QuotaLedgerEvent.RELEASE)

    metrics = collect_operational_metrics()

    assert metrics.generation_attempts == 2
    assert metrics.retried_tasks == 1
    assert metrics.automatic_retry_rate == 0.5
    assert metrics.wrong_charge_count == 0
    assert metrics.unfinished_task_count == 0


def test_operational_metrics_detect_wrong_success_charge(django_user_model):
    user, quota = create_quota(django_user_model)
    task = create_task(user, quota, status=GenerationStatus.SUCCEEDED)
    add_event(quota, task.id, QuotaLedgerEvent.RESERVE)
    add_event(quota, task.id, QuotaLedgerEvent.RELEASE)

    metrics = collect_operational_metrics()

    assert metrics.wrong_charge_count > 0


def test_operational_metrics_detect_orphan_charge(django_user_model):
    _, quota = create_quota(django_user_model, reserved_count=1)
    add_event(quota, uuid4(), QuotaLedgerEvent.RESERVE)

    metrics = collect_operational_metrics()

    assert metrics.wrong_charge_count > 0


@pytest.mark.parametrize(
    ("status", "started"),
    [
        (GenerationStatus.GENERATING, True),
        (GenerationStatus.QUOTA_RESERVED, False),
    ],
)
def test_operational_metrics_detect_unfinished_charged_tasks(
    django_user_model,
    status,
    started,
):
    user, quota = create_quota(django_user_model, reserved_count=1)
    task = create_task(user, quota, status=status, started=started)
    add_event(quota, task.id, QuotaLedgerEvent.RESERVE)

    metrics = collect_operational_metrics()

    assert metrics.unfinished_task_count == 1
    assert metrics.wrong_charge_count == 0
