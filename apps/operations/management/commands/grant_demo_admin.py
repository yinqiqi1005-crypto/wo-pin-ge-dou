from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.memberships.models import MembershipLevel, MembershipPlan
from apps.memberships.services import activate_demo_membership


class Command(BaseCommand):
    help = "Grant an existing local demo user Django admin access and the Pro membership plan."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"用户不存在：{username}")
        plan = MembershipPlan.objects.filter(
            level=MembershipLevel.PRO,
            is_active=True,
        ).first()
        if plan is None:
            raise CommandError("未找到可用的 Pro 会员方案，请先执行 seed_demo_config。")

        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save(update_fields=("is_staff", "is_superuser", "is_active"))
        activate_demo_membership(user, plan)
        self.stdout.write(self.style.SUCCESS(f"已授予 {username} 管理员和 Pro 演示权限。"))
