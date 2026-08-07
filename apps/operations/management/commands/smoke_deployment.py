from django.core.management.base import BaseCommand, CommandError

from apps.operations.deployment_smoke import (
    DeploymentSmokeError,
    run_deployment_smoke,
    save_deployment_report,
)


class Command(BaseCommand):
    help = "Smoke-test a deployed site and save a non-overwriting JSON evidence report."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", required=True)
        parser.add_argument("--expected-host", required=True)
        parser.add_argument("--report", required=True)
        parser.add_argument("--timeout", type=float, default=10)
        parser.add_argument("--allow-http-localhost", action="store_true")

    def handle(self, *args, **options):
        try:
            report = run_deployment_smoke(
                options["base_url"],
                expected_host=options["expected_host"],
                timeout=options["timeout"],
                allow_http_localhost=options["allow_http_localhost"],
            )
            save_deployment_report(report, options["report"])
        except (OSError, DeploymentSmokeError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Deployment smoke passed: {options['report']}"))
