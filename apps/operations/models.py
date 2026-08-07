from django.conf import settings
from django.db import models


class ConfigurationRevision(models.Model):
    namespace = models.CharField(max_length=80)
    key = models.CharField(max_length=120)
    version = models.PositiveIntegerField()
    value = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configuration_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("namespace", "key", "-version")
        indexes = [
            models.Index(
                fields=("namespace", "key", "is_active", "-version"),
                name="config_active_revision",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("namespace", "key", "version"),
                name="unique_configuration_revision",
            )
        ]

    def __str__(self) -> str:
        return f"{self.namespace}.{self.key} v{self.version}"
