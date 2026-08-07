from django.contrib.auth import get_user_model
from django.db import transaction

from apps.memberships.models import MembershipPlan, MembershipSubscription

from .models import GenerationMode, GenerationTask

User = get_user_model()


@transaction.atomic
def create_generation_task(
    *, user: User, idempotency_key: str, mode: str = GenerationMode.BASIC
) -> tuple[GenerationTask, bool]:
    existing = GenerationTask.objects.filter(
        user=user,
        idempotency_key=idempotency_key,
    ).first()
    if existing:
        return existing, False

    subscription = (
        MembershipSubscription.objects.select_related("plan")
        .filter(user=user, is_active=True)
        .first()
    )
    if subscription:
        plan = subscription.plan
    else:
        plan = MembershipPlan.objects.get(level="registered", is_active=True)

    task = GenerationTask.objects.create(
        user=user,
        idempotency_key=idempotency_key,
        mode=mode,
        configuration_snapshot={"membership": plan.snapshot()},
    )
    return task, True
