import csv
import mimetypes
import re
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from openai import OpenAI
from PIL import Image

from services.ai.advanced import (
    OpenAIImageEditProvider,
    review_advanced_result,
)
from services.ai.providers.openai_responses import OpenAIResponsesAnalysisProvider

REPORT_FIELDS = (
    "run_id",
    "capability",
    "model",
    "image",
    "status",
    "latency_ms",
    "error_type",
    "prompt_version",
    "primary_subject",
    "subject_count",
    "suitability",
    "recommended_grid_size",
    "recommended_color_limit",
    "output_file",
    "automated_review_status",
    "identity_score",
    "changed_ratio",
    "human_subject_correct",
    "human_region_correct",
    "human_chinese_clear",
    "human_identity_preserved",
    "human_instruction_following",
    "human_safety",
    "human_review",
    "billing_review",
)
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]+$")


def is_safe_identifier(value):
    return value not in {".", ".."} and SAFE_IDENTIFIER.fullmatch(value) is not None


class Command(BaseCommand):
    help = "Run a billable 2-3 model comparison on the same 10-15 authorized images."

    def add_arguments(self, parser):
        parser.add_argument("--capability", required=True, choices=("analysis", "advanced"))
        parser.add_argument("--models", nargs="+", required=True)
        parser.add_argument("--image-dir", required=True)
        parser.add_argument("--output-dir", default="docs/model-evaluations")
        parser.add_argument("--run-id", required=True)
        parser.add_argument("--confirm-billable", action="store_true")
        parser.add_argument("--advanced-operation", default="style_transfer")
        parser.add_argument("--advanced-instruction", default="转换为清晰的拼豆插画风格")

    def handle(self, *args, **options):
        if not options["confirm_billable"]:
            raise CommandError(
                "Refusing to call real models without --confirm-billable. API charges may apply."
            )
        models = list(dict.fromkeys(options["models"]))
        if not 2 <= len(models) <= 3:
            raise CommandError("Provide 2 or 3 unique candidate models.")
        if not is_safe_identifier(options["run_id"]):
            raise CommandError(
                "run-id may contain only letters, numbers, dot, underscore, colon or dash."
            )
        invalid_models = [model for model in models if not is_safe_identifier(model)]
        if invalid_models:
            raise CommandError("Model IDs contain unsupported path characters.")

        image_dir = Path(options["image_dir"])
        if not image_dir.is_dir():
            raise CommandError("image-dir must be an existing directory.")
        images = sorted(
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        )
        if not 10 <= len(images) <= 15:
            raise CommandError("image-dir must contain 10 to 15 JPG or PNG images.")
        if not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is required for real model evaluation.")

        output_dir = Path(options["output_dir"])
        report_path = output_dir / f"{options['run_id']}-{options['capability']}.csv"
        if report_path.exists():
            raise CommandError(f"Report already exists: {report_path}")

        client = self._build_client()
        available_models = self._available_model_ids(client)
        unavailable = [model for model in models if model not in available_models]
        if unavailable:
            raise CommandError("Configured service does not provide: " + ", ".join(unavailable))

        output_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for model in models:
            for index, image_path in enumerate(images, start=1):
                base_row = {field: "" for field in REPORT_FIELDS}
                base_row.update(
                    {
                        "run_id": options["run_id"],
                        "capability": options["capability"],
                        "model": model,
                        "image": image_path.name,
                        "human_review": "pending",
                        "billing_review": "pending_provider_invoice",
                    }
                )
                try:
                    if options["capability"] == "analysis":
                        row = self._evaluate_analysis(client, model, image_path)
                    else:
                        row = self._evaluate_advanced(
                            client,
                            model,
                            image_path,
                            output_dir=output_dir,
                            run_id=options["run_id"],
                            index=index,
                            operation=options["advanced_operation"],
                            instruction=options["advanced_instruction"],
                        )
                    base_row.update(row)
                    base_row["status"] = "success"
                except Exception as exc:  # noqa: BLE001 - each candidate failure must be isolated
                    base_row["status"] = "failed"
                    base_row["error_type"] = type(exc).__name__
                rows.append(base_row)

        with report_path.open("x", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=REPORT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        success_count = sum(row["status"] == "success" for row in rows)
        self.stdout.write(
            self.style.SUCCESS(
                f"Evaluation recorded {success_count}/{len(rows)} successful calls: {report_path}"
            )
        )

    def _build_client(self):
        return OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=max(settings.AI_ANALYSIS_TIMEOUT_SECONDS, 60),
            max_retries=0,
        )

    def _available_model_ids(self, client):
        return {model.id for model in client.models.list().data}

    def _evaluate_analysis(self, client, model, image_path):
        media_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        provider = OpenAIResponsesAnalysisProvider(
            model_name=model,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout_seconds=settings.AI_ANALYSIS_TIMEOUT_SECONDS,
            client=client,
        )
        result = provider.analyze(image_path.read_bytes(), media_type=media_type)
        analysis = result.analysis
        return {
            "latency_ms": result.latency_ms,
            "prompt_version": result.prompt_version,
            "primary_subject": analysis.primary_subject,
            "subject_count": analysis.subject_count,
            "suitability": analysis.suitability,
            "recommended_grid_size": analysis.recommendations.grid_size,
            "recommended_color_limit": analysis.recommendations.color_limit,
            "human_subject_correct": "pending",
            "human_region_correct": "pending",
            "human_chinese_clear": "pending",
        }

    def _evaluate_advanced(
        self,
        client,
        model,
        image_path,
        *,
        output_dir,
        run_id,
        index,
        operation,
        instruction,
    ):
        with Image.open(image_path) as source:
            normalized = BytesIO()
            source.convert("RGB").save(normalized, format="PNG")
        source_bytes = normalized.getvalue()
        provider = OpenAIImageEditProvider(
            model_name=model,
            timeout_seconds=max(settings.AI_ANALYSIS_TIMEOUT_SECONDS, 60),
            client=client,
        )
        result = provider.edit(
            source_bytes,
            operation=operation,
            instruction=instruction,
            preserve=["主要主体身份、姿态和关键特征"],
            editable=["背景、色彩和装饰细节"],
            region=None,
        )
        review = review_advanced_result(
            source_bytes,
            result.image_bytes,
            operation=operation,
            instruction=instruction,
        )
        model_dir = output_dir / run_id / model.replace(":", "_")
        model_dir.mkdir(parents=True, exist_ok=True)
        output_path = model_dir / f"{index:02d}-{image_path.stem}.png"
        output_path.write_bytes(result.image_bytes)
        return {
            "latency_ms": result.latency_ms,
            "prompt_version": "advanced-creation-v1.0",
            "output_file": str(output_path.relative_to(output_dir)),
            "automated_review_status": review.status,
            "identity_score": review.identity_score,
            "changed_ratio": review.changed_ratio,
            "human_identity_preserved": "pending",
            "human_instruction_following": "pending",
            "human_safety": "pending",
        }
