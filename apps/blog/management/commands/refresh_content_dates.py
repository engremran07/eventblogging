from django.core.management.base import BaseCommand

from blog.content_refresh import run_content_date_refresh


class Command(BaseCommand):
    help = "Refresh post/page updated_at based on timer settings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore interval checks and refresh now.",
        )

    def handle(self, *args, **options):
        result = run_content_date_refresh(force=options["force"])
        if not result["ran"]:
            self.stdout.write(self.style.WARNING("Refresh skipped: auto refresh is disabled."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Refresh complete: "
                f"{result['posts_updated']} posts, {result['pages_updated']} pages."
            )
        )
