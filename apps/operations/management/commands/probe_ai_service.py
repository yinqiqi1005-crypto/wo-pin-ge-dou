import re
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from openai import OpenAI

from apps.core.infrastructure_evidence import EvidenceWriteError, write_evidence

PROVIDER_PROFILES = {
    "api.deepseek.com": {
        "provider": "deepseek",
        "known_model_pattern": re.compile(r"^deepseek-v4-(?:flash|pro)$"),
        "image_analysis": False,
        "image_edit": False,
        "official_sources": [
            "https://api-docs.deepseek.com/api/list-models",
            "https://api-docs.deepseek.com/quick_start/agent_integrations/github_copilot/",
        ],
    }
}


class Command(BaseCommand):
    help = "Probe the configured model list without making billable generation calls."

    def add_arguments(self, parser):
        parser.add_argument("--report", required=True)

    def handle(self, *args, **options):
        if not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is required for the read-only service probe.")

        host = urlparse(settings.OPENAI_BASE_URL).hostname
        profile = PROVIDER_PROFILES.get(host)
        if profile is None:
            raise CommandError(
                "Configured service has no audited capability profile; refusing to guess."
            )

        client = self._build_client()
        model_ids = sorted({model.id for model in client.models.list().data})
        if not model_ids:
            raise CommandError("Configured service returned an empty model list.")
        unknown_models = [
            model_id
            for model_id in model_ids
            if profile["known_model_pattern"].fullmatch(model_id) is None
        ]
        if unknown_models:
            raise CommandError(
                "Configured service returned models outside the audited profile: "
                + ", ".join(unknown_models)
            )

        has_required_capabilities = profile["image_analysis"] and profile["image_edit"]
        try:
            write_evidence(
                options["report"],
                {
                    "check": "ai-service-capability",
                    "provider": profile["provider"],
                    "available_models": model_ids,
                    "capabilities": {
                        "image_analysis": profile["image_analysis"],
                        "image_edit": profile["image_edit"],
                    },
                    "required_capabilities_available": has_required_capabilities,
                    "request_scope": {
                        "billable_generation_calls": 0,
                        "images_uploaded": 0,
                        "models_list_calls": 1,
                    },
                    "official_sources": profile["official_sources"],
                    "result": "passed" if has_required_capabilities else "insufficient",
                },
                label="AI service capability",
            )
        except EvidenceWriteError as exc:
            raise CommandError(str(exc)) from exc

        if has_required_capabilities:
            self.stdout.write(self.style.SUCCESS("Configured AI service supports M5 and M7."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Configured AI service is reachable but lacks M5/M7 image capabilities."
                )
            )

    def _build_client(self):
        return OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=20,
            max_retries=0,
        )
