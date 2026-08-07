from django.core.management.base import BaseCommand, CommandError

from apps.operations.release_quality import ReleaseQualityError, evaluate_release_quality


class Command(BaseCommand):
    help = "Check all measurable M9 release quality gates without accepting pending reviews."

    def add_arguments(self, parser):
        parser.add_argument("--results", default="docs/test-results-40.csv")
        parser.add_argument("--generation-attempts", required=True, type=int)
        parser.add_argument("--automatic-retries", required=True, type=int)
        parser.add_argument("--wrong-charges", required=True, type=int)
        parser.add_argument("--open-critical-issues", required=True, type=int)
        parser.add_argument(
            "--deployment-smoke",
            required=True,
            choices=("passed", "failed"),
        )

    def handle(self, *args, **options):
        try:
            summary = evaluate_release_quality(
                options["results"],
                generation_attempts=options["generation_attempts"],
                automatic_retries=options["automatic_retries"],
                wrong_charges=options["wrong_charges"],
                open_critical_issues=options["open_critical_issues"],
                deployment_smoke_passed=options["deployment_smoke"] == "passed",
            )
        except (OSError, ReleaseQualityError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Release quality passed: "
                f"{summary.case_count} cases, "
                f"recognizable {summary.subject_recognizable_rate:.1%}, "
                f"severe errors {summary.severe_subject_error_rate:.1%}, "
                f"making feasible {summary.making_feasible_rate:.1%}."
            )
        )
