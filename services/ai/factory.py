from django.conf import settings

from .providers import OpenAIResponsesAnalysisProvider, RuleBasedAnalysisProvider


def get_analysis_provider(route: dict | None = None):
    route = route or {}
    provider = route.get("provider", settings.AI_ANALYSIS_PROVIDER).lower()
    if provider == "rules":
        return RuleBasedAnalysisProvider(
            grid_sizes=tuple(route.get("grid_sizes", (30, 50, 70))),
            color_limits=tuple(route.get("color_limits", (12, 24, 36))),
            background_modes=tuple(route.get("background_modes", ("keep", "simplify", "remove"))),
        )
    if provider == "openai":
        return OpenAIResponsesAnalysisProvider(
            model_name=route.get("model", settings.AI_ANALYSIS_MODEL),
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout_seconds=route.get("timeout_seconds", settings.AI_ANALYSIS_TIMEOUT_SECONDS),
            grid_sizes=tuple(route.get("grid_sizes", (30, 50, 70))),
            color_limits=tuple(route.get("color_limits", (12, 24, 36))),
            background_modes=tuple(route.get("background_modes", ("keep", "simplify", "remove"))),
        )
    raise ValueError(f"Unsupported AI analysis provider: {provider}")
