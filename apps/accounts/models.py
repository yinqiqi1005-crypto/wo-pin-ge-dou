from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=80, blank=True)
    avatar = models.ImageField(upload_to="accounts/avatars/%Y/%m/", blank=True)
    bio = models.CharField(max_length=240, blank=True)
    preferred_language = models.CharField(max_length=10, default="zh-Hans")
    default_pattern_size = models.CharField(max_length=12, default="58x58")
    default_color_limit = models.PositiveSmallIntegerField(default=24)
    default_background_mode = models.CharField(max_length=20, default="simplify")
    default_finished_use = models.CharField(max_length=30, default="unsure")
    remember_creation_parameters = models.BooleanField(default=True)
    preferred_palette_code = models.CharField(max_length=64, blank=True)
    is_guest = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.display_name or self.user.get_username()
