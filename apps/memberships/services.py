from datetime import UTC, datetime
from time import sleep

from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import F
from django.utils import timezone

from apps.creation.models import GenerationStatus, GenerationTask

from .models import (
    GenerationQuotaLedger,
    GenerationQuotaPeriod,
    MembershipLevel,
    MembershipPlan,
    MembershipSubscription,
    QuotaLedgerEvent,
    QuotaPeriodType,
)


class InsufficientGenerationQuota(ValueError):
    """Raised when a user cannot reserve another generated image."""


class InvalidQuotaState(ValueError):
    """Raised when quota settlement does not match the task state."""


def current_plan_for_user(user) -> MembershipPlan:
    subscription = (
        MembershipSubscription.objects.select_related("plan")
        .filter(user=user, is_active=True)
        .first()
    )
    if subscription:
        return subscription.plan
    return MembershipPlan.objects.get(level=MembershipLevel.REGISTERED, is_active=True)


def _period_boundaries(plan: MembershipPlan) -> tuple[datetime, datetime | None]:
    if plan.quota_period == QuotaPeriodType.LIFETIME:
        return datetime(2000, 1, 1, tzinfo=UTC), None

    now = timezone.localtime()
    starts_at = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if starts_at.month == 12:
        ends_at = starts_at.replace(year=starts_at.year + 1, month=1)
    else:
        ends_at = starts_at.replace(month=starts_at.month + 1)
    return starts_at, ends_at


@transaction.atomic
def get_or_create_current_quota(user) -> GenerationQuotaPeriod:
    plan = current_plan_for_user(user)
    starts_at, ends_at = _period_boundaries(plan)
    try:
        quota, created = GenerationQuotaPeriod.objects.get_or_create(
            user=user,
            starts_at=starts_at,
            defaults={
                "plan": plan,
                "ends_at": ends_at,
                "total_limit": plan.generation_limit,
            },
        )
    except IntegrityError:
        quota = GenerationQuotaPeriod.objects.get(user=user, starts_at=starts_at)
        created = False

    if created:
        GenerationQuotaLedger.objects.create(
            quota_period=quota,
            event=QuotaLedgerEvent.ALLOCATE,
            amount=quota.total_limit,
            idempotency_key=f"quota:{quota.pk}:allocate",
            reason=f"{plan.name} 周期生成张数",
        )
    return quota


def reserve_generation(task: GenerationTask, *, amount: int = 1) -> GenerationQuotaPeriod:
    attempts = 3 if connection.vendor == "sqlite" else 1
    for attempt in range(attempts):
        try:
            return _reserve_generation_atomic(task, amount=amount)
        except OperationalError as exc:
            is_transient_sqlite_lock = (
                connection.vendor == "sqlite" and "locked" in str(exc).lower()
            )
            if not is_transient_sqlite_lock or attempt + 1 == attempts:
                raise
            sleep(0.02 * (attempt + 1))
    raise RuntimeError("Quota reservation retry loop ended unexpectedly.")


@transaction.atomic
def _reserve_generation_atomic(task: GenerationTask, *, amount: int = 1) -> GenerationQuotaPeriod:
    if amount <= 0:
        raise ValueError("Reservation amount must be positive.")
    key = f"task:{task.pk}:reserve"
    existing = GenerationQuotaLedger.objects.filter(idempotency_key=key).first()
    if existing:
        return existing.quota_period

    quota = get_or_create_current_quota(task.user)
    updated = GenerationQuotaPeriod.objects.filter(
        pk=quota.pk,
        total_limit__gte=F("used_count") + F("reserved_count") + amount,
    ).update(reserved_count=F("reserved_count") + amount)
    if updated != 1:
        raise InsufficientGenerationQuota("你本周期的生成张数已经用完。")

    GenerationQuotaLedger.objects.create(
        quota_period=quota,
        task_reference=task.pk,
        event=QuotaLedgerEvent.RESERVE,
        amount=amount,
        idempotency_key=key,
        reason="开始生成前预留",
    )
    task.quota_period = quota
    task.status = GenerationStatus.QUOTA_RESERVED
    task.save(update_fields=("quota_period", "status", "updated_at"))
    quota.refresh_from_db()
    return quota


@transaction.atomic
def consume_generation(task: GenerationTask, *, amount: int = 1) -> GenerationQuotaPeriod:
    key = f"task:{task.pk}:consume"
    existing = GenerationQuotaLedger.objects.filter(idempotency_key=key).first()
    if existing:
        return existing.quota_period
    if task.quota_period_id is None:
        raise InvalidQuotaState("任务没有预留生成张数。")

    quota = GenerationQuotaPeriod.objects.select_for_update().get(pk=task.quota_period_id)
    updated = GenerationQuotaPeriod.objects.filter(
        pk=quota.pk,
        reserved_count__gte=amount,
    ).update(
        reserved_count=F("reserved_count") - amount,
        used_count=F("used_count") + amount,
    )
    if updated != 1:
        raise InvalidQuotaState("任务预留张数不足，无法完成结算。")

    GenerationQuotaLedger.objects.create(
        quota_period=quota,
        task_reference=task.pk,
        event=QuotaLedgerEvent.CONSUME,
        amount=amount,
        idempotency_key=key,
        reason="图纸生成成功",
    )
    quota.refresh_from_db()
    return quota


@transaction.atomic
def release_generation(task: GenerationTask, *, amount: int = 1) -> GenerationQuotaPeriod | None:
    key = f"task:{task.pk}:release"
    existing = GenerationQuotaLedger.objects.filter(idempotency_key=key).first()
    if existing:
        return existing.quota_period
    if task.quota_period_id is None:
        return None
    if GenerationQuotaLedger.objects.filter(idempotency_key=f"task:{task.pk}:consume").exists():
        raise InvalidQuotaState("已经正式使用的生成张数不能释放。")

    quota = GenerationQuotaPeriod.objects.select_for_update().get(pk=task.quota_period_id)
    updated = GenerationQuotaPeriod.objects.filter(
        pk=quota.pk,
        reserved_count__gte=amount,
    ).update(reserved_count=F("reserved_count") - amount)
    if updated != 1:
        raise InvalidQuotaState("任务没有可释放的预留张数。")

    GenerationQuotaLedger.objects.create(
        quota_period=quota,
        task_reference=task.pk,
        event=QuotaLedgerEvent.RELEASE,
        amount=amount,
        idempotency_key=key,
        reason="系统生成失败或排队取消",
    )
    quota.refresh_from_db()
    return quota
