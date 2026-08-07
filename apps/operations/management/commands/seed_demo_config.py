from django.core.management.base import BaseCommand
from django.db import transaction

from apps.memberships.models import (
    Feature,
    FeatureCode,
    MembershipLevel,
    MembershipPlan,
    QuotaPeriodType,
)
from apps.operations.models import ConfigurationRevision
from apps.patterns.models import Palette, PaletteColor
from services.image_processing.palette import DEFAULT_PALETTE

FEATURES = {
    FeatureCode.BASIC_GENERATION: "基础生成",
    FeatureCode.STYLE_TRANSFER: "风格转换",
    FeatureCode.MULTI_SUBJECT: "多主体处理",
    FeatureCode.COMPOSITION: "构图调整",
    FeatureCode.BACKGROUND_CREATION: "背景创作",
    FeatureCode.ELEMENT_EDIT: "元素增删",
    FeatureCode.LOCAL_EDIT: "局部重绘",
    FeatureCode.ADVANCED_GUIDANCE: "高级制作辅助",
}

# These values are demo defaults, not permanent commercial decisions. Admins can
# edit them after seeding without changing application code.
PLANS = {
    MembershipLevel.VISITOR: {
        "name": "免费游客",
        "quota_period": QuotaPeriodType.LIFETIME,
        "generation_limit": 1,
        "priority": 0,
        "features": (FeatureCode.BASIC_GENERATION,),
    },
    MembershipLevel.REGISTERED: {
        "name": "注册会员",
        "quota_period": QuotaPeriodType.MONTHLY,
        "generation_limit": 10,
        "priority": 10,
        "features": (FeatureCode.BASIC_GENERATION,),
    },
    MembershipLevel.PLUS: {
        "name": "Plus 会员",
        "quota_period": QuotaPeriodType.MONTHLY,
        "generation_limit": 60,
        "priority": 20,
        "features": (
            FeatureCode.BASIC_GENERATION,
            FeatureCode.STYLE_TRANSFER,
            FeatureCode.MULTI_SUBJECT,
            FeatureCode.COMPOSITION,
            FeatureCode.ADVANCED_GUIDANCE,
        ),
    },
    MembershipLevel.PRO: {
        "name": "Pro 会员",
        "quota_period": QuotaPeriodType.MONTHLY,
        "generation_limit": 200,
        "priority": 30,
        "features": tuple(FEATURES),
    },
}


class Command(BaseCommand):
    help = "Create or update configurable demo membership plans and the generic palette."

    @transaction.atomic
    def handle(self, *args, **options):
        feature_objects = {}
        for code, name in FEATURES.items():
            feature, _ = Feature.objects.update_or_create(
                code=code,
                defaults={"name": name, "is_active": True},
            )
            feature_objects[code] = feature

        for level, values in PLANS.items():
            feature_codes = values["features"]
            plan, _ = MembershipPlan.objects.update_or_create(
                level=level,
                defaults={
                    "name": values["name"],
                    "quota_period": values["quota_period"],
                    "generation_limit": values["generation_limit"],
                    "priority": values["priority"],
                    "is_active": True,
                },
            )
            plan.features.set(feature_objects[code] for code in feature_codes)

        palette, _ = Palette.objects.update_or_create(
            code=DEFAULT_PALETTE.code,
            defaults={
                "name": DEFAULT_PALETTE.name,
                "version": "1",
                "is_active": True,
                "is_default": True,
            },
        )
        for index, color in enumerate(DEFAULT_PALETTE.colors, start=1):
            PaletteColor.objects.update_or_create(
                palette=palette,
                code=color.code,
                defaults={
                    "name": color.name,
                    "red": color.rgb[0],
                    "green": color.rgb[1],
                    "blue": color.rgb[2],
                    "sort_order": index,
                    "is_active": True,
                },
            )

        ConfigurationRevision.objects.get_or_create(
            namespace="model_routes",
            key="analysis",
            version=1,
            defaults={
                "value": {
                    "provider": "rules",
                    "model": "gpt-5.6-luna",
                    "fallback_provider": "rules",
                    "timeout_seconds": 20,
                    "max_attempts": 2,
                    "simulated_cost_per_call": "0.006000",
                },
                "is_active": True,
            },
        )
        ConfigurationRevision.objects.get_or_create(
            namespace="generation",
            key="enabled_options",
            version=1,
            defaults={
                "value": {
                    "grid_sizes": [30, 50, 70],
                    "color_limits": [12, 24, 36],
                    "background_modes": ["keep", "simplify", "remove"],
                },
                "is_active": True,
            },
        )
        ConfigurationRevision.objects.get_or_create(
            namespace="quality",
            key="generation_policy",
            version=1,
            defaults={
                "value": {
                    "analysis_max_attempts": 2,
                    "generation_max_attempts": 2,
                    "advanced_max_attempts": 2,
                    "max_upload_mb": 10,
                },
                "is_active": True,
            },
        )
        ConfigurationRevision.objects.get_or_create(
            namespace="model_routes",
            key="advanced_creation",
            version=1,
            defaults={
                "value": {
                    "provider": "mock",
                    "model": "deterministic-edit-v1",
                    "production_model": "gpt-image-2",
                    "timeout_seconds": 60,
                    "max_attempts": 2,
                    "simulated_cost_per_call": "0.040000",
                },
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo configuration is ready."))
