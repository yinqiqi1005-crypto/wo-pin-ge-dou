import uuid

from django.conf import settings
from django.db import models


class GenerationMode(models.TextChoices):
    BASIC = "basic", "基础生成"
    ADVANCED = "advanced", "高级创作"


class GenerationStatus(models.TextChoices):
    UPLOADED = "uploaded", "等待分析"
    ANALYZING = "analyzing", "正在分析"
    AWAITING_CONFIRMATION = "awaiting_confirmation", "等待用户确认"
    QUOTA_RESERVED = "quota_reserved", "已预留生成张数"
    QUEUED = "queued", "排队中"
    GENERATING = "generating", "生成中"
    VALIDATING = "validating", "正在校验"
    SUCCEEDED = "succeeded", "生成成功"
    SAVED = "saved", "保存成功"
    FAILED = "failed", "生成失败"
    CANCELLED = "cancelled", "已取消"


class GenerationTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="generation_tasks",
    )
    status = models.CharField(
        max_length=40,
        choices=GenerationStatus,
        default=GenerationStatus.UPLOADED,
    )
    mode = models.CharField(max_length=20, choices=GenerationMode, default=GenerationMode.BASIC)
    input_image = models.ImageField(upload_to="creation/input/%Y/%m/", blank=True)
    idempotency_key = models.CharField(max_length=120)
    configuration_snapshot = models.JSONField(default=dict)
    current_stage = models.CharField(max_length=80, blank=True)
    progress_message = models.CharField(max_length=240, blank=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    quota_period = models.ForeignKey(
        "memberships.GenerationQuotaPeriod",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tasks",
    )
    result_version = models.ForeignKey(
        "patterns.PatternVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "idempotency_key"),
                name="unique_user_generation_idempotency_key",
            )
        ]

    def __str__(self) -> str:
        return f"{self.id} · {self.get_status_display()}"


class ImageAnalysisResult(models.Model):
    task = models.OneToOneField(GenerationTask, on_delete=models.CASCADE, related_name="analysis")
    quality_level = models.CharField(max_length=40)
    suitability_level = models.CharField(max_length=40)
    primary_subject = models.CharField(max_length=120, blank=True)
    subject_count = models.PositiveSmallIntegerField(default=0)
    subject_region = models.JSONField(default=dict)
    confidence_level = models.CharField(max_length=20, blank=True)
    issues = models.JSONField(default=list)
    recommendations = models.JSONField(default=dict)
    requires_subject_confirmation = models.BooleanField(default=False)
    model_name = models.CharField(max_length=120, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.task_id} · {self.primary_subject or '未识别主体'}"


class GenerationSettings(models.Model):
    task = models.OneToOneField(GenerationTask, on_delete=models.CASCADE, related_name="settings")
    selected_subject = models.JSONField(default=dict)
    crop = models.JSONField(default=dict)
    grid_size = models.PositiveSmallIntegerField(default=50)
    color_limit = models.PositiveSmallIntegerField(default=24)
    background_mode = models.CharField(max_length=20, default="simplify")
    style = models.CharField(max_length=80, blank=True)
    creative_instruction = models.TextField(blank=True)
    preserve_content = models.JSONField(default=list)
    editable_content = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.task_id} · {self.grid_size}×{self.grid_size}"


class ModelCapability(models.TextChoices):
    ANALYSIS = "analysis", "图片分析"
    SEGMENTATION = "segmentation", "主体分割"
    IMAGE_EDIT = "image_edit", "图像创作"
    VISUAL_REVIEW = "visual_review", "视觉复查"
    GUIDANCE = "guidance", "制作建议"


class ModelCallLog(models.Model):
    task = models.ForeignKey(GenerationTask, on_delete=models.CASCADE, related_name="model_calls")
    capability = models.CharField(max_length=30, choices=ModelCapability)
    provider = models.CharField(max_length=80)
    model_name = models.CharField(max_length=120)
    prompt_version = models.CharField(max_length=40, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=False)
    retry_number = models.PositiveSmallIntegerField(default=0)
    internal_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    error_type = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.task_id} · {self.capability} · {self.model_name}"
