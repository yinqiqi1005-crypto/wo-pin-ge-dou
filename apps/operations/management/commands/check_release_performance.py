from django.core.management.base import BaseCommand, CommandError

from apps.operations.release_performance import (
    ReleasePerformanceError,
    run_release_performance,
    save_release_performance_report,
)


class Command(BaseCommand):
    help = "Measure deterministic upload, analysis, generation and export release baselines."

    def add_arguments(self, parser):
        parser.add_argument("--report", required=True)
        parser.add_argument("--iterations", type=int, default=3)

    def handle(self, *args, **options):
        try:
            report = run_release_performance(iterations=options["iterations"])
            save_release_performance_report(report, options["report"])
        except (OSError, ReleasePerformanceError) as exc:
            raise CommandError(str(exc)) from exc

        measurements = ", ".join(
            f"{stage.name}={stage.maximum_seconds:.3f}s" for stage in report.stages
        )
        self.stdout.write(self.style.SUCCESS(f"Release performance passed: {measurements}."))
