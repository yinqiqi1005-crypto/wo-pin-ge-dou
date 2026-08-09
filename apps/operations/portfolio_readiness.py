from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.test import Client
from PIL import Image, UnidentifiedImageError

from apps.memberships.models import FeatureCode, MembershipLevel, MembershipPlan
from apps.memberships.services import current_plan_for_user
from apps.operations.models import ConfigurationRevision
from services.image_processing.pipeline import create_pattern

DEMO_ACCOUNTS = {
    "demo_registered": MembershipLevel.REGISTERED,
    "demo_plus": MembershipLevel.PLUS,
    "demo_pro": MembershipLevel.PRO,
}
DEMO_ASSETS = (
    "demo-assets/demo-person.png",
    "demo-assets/demo-pet.png",
    "demo-assets/demo-object.png",
)
REQUIRED_PLAN_FEATURES = {
    MembershipLevel.VISITOR: {FeatureCode.BASIC_GENERATION},
    MembershipLevel.REGISTERED: {FeatureCode.BASIC_GENERATION},
    MembershipLevel.PLUS: {
        FeatureCode.BASIC_GENERATION,
        FeatureCode.STYLE_TRANSFER,
        FeatureCode.MULTI_SUBJECT,
        FeatureCode.COMPOSITION,
    },
    MembershipLevel.PRO: set(FeatureCode.values),
}


class PortfolioReadinessError(ValueError):
    pass


def _active_configuration(namespace, key):
    return (
        ConfigurationRevision.objects.filter(
            namespace=namespace,
            key=key,
            is_active=True,
        )
        .order_by("-version")
        .first()
    )


def evaluate_portfolio_readiness():
    errors = []
    if not settings.SERVE_MEDIA:
        errors.append("Local portfolio demo must serve uploaded media previews")
    plans = {plan.level: plan for plan in MembershipPlan.objects.prefetch_related("features")}
    for level, required_features in REQUIRED_PLAN_FEATURES.items():
        plan = plans.get(level)
        if plan is None or not plan.is_active:
            errors.append(f"Missing active membership plan: {level}")
            continue
        if plan.generation_limit <= 0:
            errors.append(f"Membership plan has no generation images: {level}")
        active_features = set(plan.features.filter(is_active=True).values_list("code", flat=True))
        if not required_features.issubset(active_features):
            errors.append(f"Membership plan lacks portfolio features: {level}")

    routes = {}
    for key, expected_provider in (("analysis", "rules"), ("advanced_creation", "mock")):
        revision = _active_configuration("model_routes", key)
        if revision is None:
            errors.append(f"Missing active model route: {key}")
            continue
        provider = revision.value.get("provider")
        routes[key] = provider
        if provider != expected_provider:
            errors.append(
                f"Portfolio route {key} must use {expected_provider}, got {provider or 'empty'}"
            )

    enabled_options = _active_configuration("generation", "enabled_options")
    if enabled_options is None:
        errors.append("Missing active generation options")
    else:
        values = enabled_options.value
        if values.get("grid_sizes") != [30, 50, 70]:
            errors.append("Portfolio grid sizes must be 30, 50 and 70")
        if values.get("color_limits") != [12, 18, 24, 30, 36]:
            errors.append("Portfolio color limits must cover 12, 18, 24, 30 and 36")

    user_model = get_user_model()
    account_levels = {}
    for username, expected_level in DEMO_ACCOUNTS.items():
        user = user_model.objects.filter(username=username, is_active=True).first()
        if user is None:
            errors.append(f"Missing active demo account: {username}")
            continue
        if not user.has_usable_password():
            errors.append(f"Demo account has no usable password: {username}")
            continue
        actual_level = current_plan_for_user(user).level
        account_levels[username] = actual_level
        if actual_level != expected_level:
            errors.append(f"Demo account {username} uses {actual_level}, expected {expected_level}")

    patterns = []
    for path in DEMO_ASSETS:
        if not default_storage.exists(path):
            errors.append(f"Missing demo image: {path}")
            continue
        try:
            with default_storage.open(path, "rb") as source:
                image_bytes = source.read()
            with Image.open(BytesIO(image_bytes)) as image:
                image.verify()
            result = create_pattern(BytesIO(image_bytes), size=30, color_limit=12)
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            errors.append(f"Demo image cannot generate a pattern: {path} ({type(exc).__name__})")
            continue
        patterns.append(
            {
                "asset": path,
                "grid_size": result.grid.width,
                "color_count": result.grid.color_count,
                "total_beads": result.total_beads,
            }
        )

    page_checks = {}
    client = Client(HTTP_HOST="127.0.0.1")
    for path, marker in (
        ("/", "把喜欢的图片"),
        ("/health/", '"status": "ok"'),
        ("/accounts/login/", "登录"),
    ):
        response = client.get(path)
        content = response.content.decode("utf-8")
        page_checks[path] = response.status_code
        if response.status_code != 200 or marker not in content:
            errors.append(f"Portfolio page is unavailable: {path}")

    if errors:
        raise PortfolioReadinessError("; ".join(errors) + ".")

    return {
        "check": "portfolio-demo-readiness",
        "profile": "local-offline-portfolio",
        "result": "passed",
        "portfolio_demo_requires_external_validation": False,
        "production_validation_status": "not_evaluated",
        "media_serving_enabled": settings.SERVE_MEDIA,
        "membership_levels": sorted(plans),
        "demo_accounts": account_levels,
        "model_routes": routes,
        "generated_patterns": patterns,
        "page_checks": page_checks,
    }
