from django.core.management.base import BaseCommand, CommandError

from apps.operations.release_evidence import (
    ReleaseEvidenceError,
    collect_operational_metrics,
    count_open_critical_issues,
)
from apps.operations.release_quality import ReleaseQualityError, evaluate_release_quality


class Command(BaseCommand):
    help = "Check all measurable M9 release quality gates without accepting pending reviews."

    def add_arguments(self, parser):
        parser.add_argument("--results", default="docs/test-results-40.csv")
        parser.add_argument("--physical-results", default="docs/physical-validation.csv")
        parser.add_argument("--issues", default="docs/issues.csv")
        parser.add_argument("--deployment-report", required=True)

    def handle(self, *args, **options):
        try:
            operational_metrics = collect_operational_metrics()
            open_critical_issues = count_open_critical_issues(options["issues"])
            summary = evaluate_release_quality(
                options["results"],
                operational_metrics=operational_metrics,
                open_critical_issues=open_critical_issues,
                deployment_report_path=options["deployment_report"],
                physical_results_path=options["physical_results"],
            )
        except (OSError, ReleaseEvidenceError, ReleaseQualityError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Release quality passed: "
                f"{summary.case_count} cases, "
                f"recognizable {summary.subject_recognizable_rate:.1%}, "
                f"severe errors {summary.severe_subject_error_rate:.1%}, "
                f"making feasible {summary.making_feasible_rate:.1%}."
                f" Physical builds {summary.physical_case_count}."
            )
        )
