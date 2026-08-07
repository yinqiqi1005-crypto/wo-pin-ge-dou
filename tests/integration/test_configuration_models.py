from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.creation.models import GenerationMode, GenerationTask, ModelCallLog
from apps.creation.services import create_generation_task
from apps.memberships.models import (
    Feature,
    FeatureCode,
    GenerationQuotaLedger,
    GenerationQuotaPeriod,
    MembershipLevel,
    MembershipPlan,
    MembershipSubscription,
    QuotaLedgerEvent,
    QuotaPeriodType,
)
from apps.operations.models import ConfigurationRevision
from apps.patterns.models import Palette, Pattern, PatternVersion

pytestmark = pytest.mark.django_db


def create_plan(level=MembershipLevel.REGISTERED, *, limit=10):
    return MembershipPlan.objects.create(
        level=level,
        name=MembershipLevel(level).label,
        quota_period=QuotaPeriodType.MONTHLY,
        generation_limit=limit,
        priority=10,
    )


def test_seed_demo_config_is_repeatable():
    call_command("seed_demo_config")
    call_command("seed_demo_config")

    assert MembershipPlan.objects.count() == 4
    assert Feature.objects.count() == len(FeatureCode)
    assert Palette.objects.get(is_default=True).colors.count() == 36
    assert MembershipPlan.objects.get(level=MembershipLevel.PRO).features.count() == len(
        FeatureCode
    )
    route = ConfigurationRevision.objects.get(namespace="model_routes", key="analysis")
    assert route.value["provider"] == "rules"
    assert route.value["model"] == "gpt-5.6-luna"


def test_membership_permissions_come_from_database_configuration():
    plan = create_plan()
    feature = Feature.objects.create(code=FeatureCode.BASIC_GENERATION, name="基础生成")

    assert plan.has_feature(FeatureCode.BASIC_GENERATION) is False

    plan.features.add(feature)

    assert plan.has_feature(FeatureCode.BASIC_GENERATION) is True


def test_generation_task_keeps_membership_configuration_snapshot(django_user_model):
    user = django_user_model.objects.create_user(username="snapshot-user")
    plan = create_plan(limit=10)
    feature = Feature.objects.create(code=FeatureCode.BASIC_GENERATION, name="基础生成")
    plan.features.add(feature)
    MembershipSubscription.objects.create(
        user=user,
        plan=plan,
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(days=30),
    )

    task, created = create_generation_task(
        user=user,
        idempotency_key="snapshot-1",
        mode=GenerationMode.BASIC,
    )
    plan.generation_limit = 99
    plan.save(update_fields=("generation_limit", "updated_at"))

    assert created is True
    assert task.configuration_snapshot["membership"]["generation_limit"] == 10
    assert task.configuration_snapshot["membership"]["features"] == [FeatureCode.BASIC_GENERATION]


def test_generation_task_keeps_model_route_snapshot(django_user_model):
    call_command("seed_demo_config", verbosity=0)
    user = django_user_model.objects.create_user(username="route-snapshot-user")
    task, _ = create_generation_task(user=user, idempotency_key="route-snapshot")
    route = ConfigurationRevision.objects.get(namespace="model_routes", key="analysis")
    route.value["model"] = "changed-after-task-created"
    route.save(update_fields=("value",))

    assert task.configuration_snapshot["model_routes"]["analysis"]["model"] == "gpt-5.6-luna"


def test_generation_task_creation_is_idempotent(django_user_model):
    user = django_user_model.objects.create_user(username="idempotent-user")
    create_plan()

    first, first_created = create_generation_task(user=user, idempotency_key="same-request")
    second, second_created = create_generation_task(user=user, idempotency_key="same-request")

    assert first_created is True
    assert second_created is False
    assert first.pk == second.pk
    assert user.generation_tasks.count() == 1


def test_quota_period_rejects_usage_above_total(django_user_model):
    user = django_user_model.objects.create_user(username="quota-user")
    plan = create_plan(limit=2)
    quota = GenerationQuotaPeriod(
        user=user,
        plan=plan,
        starts_at=timezone.now(),
        total_limit=2,
        used_count=2,
        reserved_count=1,
    )

    with pytest.raises(ValidationError, match="不能超过"):
        quota.full_clean()


def test_database_constraint_prevents_quota_overuse(django_user_model):
    user = django_user_model.objects.create_user(username="db-quota-user")
    plan = create_plan(limit=2)

    with pytest.raises(IntegrityError), transaction.atomic():
        GenerationQuotaPeriod.objects.create(
            user=user,
            plan=plan,
            starts_at=timezone.now(),
            total_limit=2,
            used_count=2,
            reserved_count=1,
        )


def test_quota_ledger_idempotency_key_is_unique(django_user_model):
    user = django_user_model.objects.create_user(username="ledger-user")
    plan = create_plan(limit=2)
    quota = GenerationQuotaPeriod.objects.create(
        user=user,
        plan=plan,
        starts_at=timezone.now(),
        total_limit=2,
    )
    GenerationQuotaLedger.objects.create(
        quota_period=quota,
        task_reference=uuid4(),
        event=QuotaLedgerEvent.RESERVE,
        amount=1,
        idempotency_key="quota-operation",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        GenerationQuotaLedger.objects.create(
            quota_period=quota,
            task_reference=uuid4(),
            event=QuotaLedgerEvent.RESERVE,
            amount=1,
            idempotency_key="quota-operation",
        )


def test_pattern_versions_belong_to_the_same_pattern(django_user_model):
    user = django_user_model.objects.create_user(username="pattern-user")
    first_pattern = Pattern.objects.create(owner=user, title="First")
    second_pattern = Pattern.objects.create(owner=user, title="Second")
    first_version = PatternVersion.objects.create(pattern=first_pattern, version_number=1)
    invalid_version = PatternVersion(
        pattern=second_pattern,
        version_number=1,
        parent_version=first_version,
    )

    with pytest.raises(ValidationError, match="同一个作品"):
        invalid_version.full_clean()


def test_pattern_query_can_be_scoped_to_owner(django_user_model):
    first_user = django_user_model.objects.create_user(username="owner-one")
    second_user = django_user_model.objects.create_user(username="owner-two")
    Pattern.objects.create(owner=first_user, title="Visible")
    Pattern.objects.create(owner=second_user, title="Hidden")

    visible_titles = list(Pattern.objects.filter(owner=first_user).values_list("title", flat=True))

    assert visible_titles == ["Visible"]


def test_configuration_revision_is_unique_per_version(django_user_model):
    admin_user = django_user_model.objects.create_superuser(
        username="config-admin",
        email="admin@example.com",
        password="safe-test-password",
    )
    ConfigurationRevision.objects.create(
        namespace="generation",
        key="grid_sizes",
        version=1,
        value={"sizes": [30, 50, 70]},
        created_by=admin_user,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ConfigurationRevision.objects.create(
            namespace="generation",
            key="grid_sizes",
            version=1,
            value={"sizes": [30]},
            created_by=admin_user,
        )


def test_high_volume_business_queries_have_explicit_database_indexes():
    assert {index.name for index in GenerationTask._meta.indexes} >= {
        "task_user_status_created",
        "task_status_created",
    }
    assert {index.name for index in ModelCallLog._meta.indexes} >= {"model_call_cap_success"}
    assert {index.name for index in Pattern._meta.indexes} >= {"pattern_owner_library"}
    assert {index.name for index in ConfigurationRevision._meta.indexes} >= {
        "config_active_revision"
    }
