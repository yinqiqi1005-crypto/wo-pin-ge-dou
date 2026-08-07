from django.core.management.base import BaseCommand, CommandError

from apps.operations.human_review import HumanReviewPackError, build_human_review_pack


class Command(BaseCommand):
    help = "Build a non-overwriting 40-case human review pack without inventing scores."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--results", default="docs/test-results-40.csv")

    def handle(self, *args, **options):
        try:
            destination = build_human_review_pack(
                options["output_dir"],
                results_path=options["results"],
            )
        except (OSError, HumanReviewPackError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Human review pack created: {destination}"))
