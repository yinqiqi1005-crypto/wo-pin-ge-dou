from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "preferred_palette_code", "updated_at")
    search_fields = ("user__username", "display_name")
