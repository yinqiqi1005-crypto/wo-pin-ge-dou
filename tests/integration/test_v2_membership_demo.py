import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.memberships.models import MembershipLevel, MembershipSubscription
from apps.memberships.services import get_or_create_current_quota

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


def test_membership_plan_page_explains_all_four_levels(client):
    response = client.get(reverse("memberships:plans"))

    assert response.status_code == 200
    page = response.content.decode()
    for label in ("免费游客", "注册会员", "Plus 会员", "Pro 会员"):
        assert label in page
    assert "模拟升级" in page


def test_logged_in_user_can_simulate_upgrade_and_sees_new_quota(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="upgrade-user", password="safe-password-123"
    )
    initial_quota = get_or_create_current_quota(user)
    client.force_login(user)

    response = client.post(reverse("memberships:upgrade", args=(MembershipLevel.PLUS,)))

    assert response.status_code == 302
    subscription = MembershipSubscription.objects.get(user=user)
    assert subscription.plan.level == MembershipLevel.PLUS
    initial_quota.refresh_from_db()
    assert initial_quota.plan.level == MembershipLevel.PLUS
    assert initial_quota.total_limit >= 60

    center = client.get(reverse("memberships:center"))
    assert center.status_code == 200
    assert "Plus 会员" in center.content.decode()
    assert "剩余生成张数" in center.content.decode()


def test_upgrade_requires_login_and_inactive_plan_cannot_be_selected(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="inactive-upgrade-user", password="safe-password-123"
    )
    assert (
        client.post(reverse("memberships:upgrade", args=(MembershipLevel.PRO,))).status_code == 302
    )

    client.force_login(user)
    from apps.memberships.models import MembershipPlan

    plan = MembershipPlan.objects.get(level=MembershipLevel.PRO)
    plan.is_active = False
    plan.save(update_fields=("is_active", "updated_at"))

    assert (
        client.post(reverse("memberships:upgrade", args=(MembershipLevel.PRO,))).status_code == 404
    )
