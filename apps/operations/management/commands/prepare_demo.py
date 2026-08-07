from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.memberships.models import MembershipPlan, MembershipSubscription
from services.demo_assets import build_demo_images


class Command(BaseCommand):
    help = "Create registered, Plus and Pro demo accounts and three stable demo images."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True)

    def handle(self, *args, **options):
        password = options["password"]
        if len(password) < 12:
            raise CommandError("Demo password must contain at least 12 characters.")
        user_model = get_user_model()
        accounts = (
            ("demo_registered", "registered"),
            ("demo_plus", "plus"),
            ("demo_pro", "pro"),
        )
        for username, level in accounts:
            user, _ = user_model.objects.get_or_create(username=username)
            user.set_password(password)
            user.save(update_fields=("password",))
            plan = MembershipPlan.objects.get(level=level, is_active=True)
            if level != "registered":
                MembershipSubscription.objects.update_or_create(
                    user=user,
                    defaults={
                        "plan": plan,
                        "starts_at": timezone.now(),
                        "ends_at": timezone.now() + timedelta(days=30),
                        "is_active": True,
                    },
                )

        for filename, _, content in build_demo_images():
            path = f"demo-assets/{filename}"
            if default_storage.exists(path):
                default_storage.delete(path)
            default_storage.save(path, ContentFile(content))

        self.stdout.write(
            self.style.SUCCESS(f"Demo accounts and images are ready under {settings.MEDIA_ROOT}.")
        )
