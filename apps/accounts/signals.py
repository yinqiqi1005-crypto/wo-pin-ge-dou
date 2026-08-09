from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.patterns.categories import ensure_user_categories

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_and_categories(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        ensure_user_categories(instance)
