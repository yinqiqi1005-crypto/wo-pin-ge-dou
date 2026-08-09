import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.memberships.services import current_plan_for_user, get_or_create_current_quota

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


def test_grant_demo_admin_makes_an_existing_user_staff_superuser_and_pro(django_user_model):
    user = django_user_model.objects.create_user(username="portfolio-admin")

    call_command("grant_demo_admin", username=user.username, verbosity=0)

    user.refresh_from_db()
    quota = get_or_create_current_quota(user)
    assert user.is_staff is True
    assert user.is_superuser is True
    assert current_plan_for_user(user).level == "pro"
    assert quota.plan.level == "pro"


def test_grant_demo_admin_requires_an_existing_user():
    with pytest.raises(CommandError, match="不存在"):
        call_command("grant_demo_admin", username="missing-demo-user", verbosity=0)
