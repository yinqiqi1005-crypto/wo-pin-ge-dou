from django.core.management.base import BaseCommand, CommandError

from apps.core.infrastructure_evidence import EvidenceWriteError, write_evidence
from apps.operations.usability_walkthrough import (
    UsabilityWalkthroughError,
    evaluate_usability_walkthrough,
)


class Command(BaseCommand):
    help = "Validate the first complete external-human usability walkthrough."

    def add_arguments(self, parser):
        parser.add_argument("--results", default="docs/usability-walkthrough.csv")
        parser.add_argument("--report")

    def handle(self, *args, **options):
        try:
            summary = evaluate_usability_walkthrough(options["results"])
            write_evidence(
                options.get("report"),
                {
                    "check": "first-usability-walkthrough",
                    "participant_type": "external_human",
                    "task_count": summary.task_count,
                    "total_seconds": summary.total_seconds,
                    "total_assistance_count": summary.total_assistance_count,
                    "device": summary.device,
                    "result": "passed",
                },
                label="usability walkthrough",
            )
        except (OSError, EvidenceWriteError, UsabilityWalkthroughError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Usability walkthrough passed: {summary.task_count} tasks on {summary.device}."
            )
        )
