from django.core.management.base import BaseCommand, CommandError

from apps.core.infrastructure_evidence import EvidenceWriteError, write_evidence
from apps.operations.portfolio_readiness import (
    PortfolioReadinessError,
    evaluate_portfolio_readiness,
)


class Command(BaseCommand):
    help = "Check whether the local offline portfolio demo is ready to present."

    def add_arguments(self, parser):
        parser.add_argument("--report")

    def handle(self, *args, **options):
        try:
            report = evaluate_portfolio_readiness()
            write_evidence(
                options.get("report"),
                report,
                label="portfolio demo",
            )
        except (EvidenceWriteError, PortfolioReadinessError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Portfolio demo is ready: 4 membership levels, 3 demo accounts, "
                "3 generated patterns, offline analysis and advanced creation routes."
            )
        )
