from __future__ import annotations

from django.core.management.base import BaseCommand

from blog.models import Post
from blog.services import apply_auto_taxonomy_to_post


class Command(BaseCommand):
    help = "Recompute deterministic auto-tagging for existing posts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional max number of posts to process.",
        )
        parser.add_argument(
            "--only-published",
            action="store_true",
            help="Process only published posts.",
        )

    def handle(self, *args, **options):
        queryset = Post.objects.all().order_by("-updated_at")
        if options["only_published"]:
            queryset = queryset.filter(status=Post.Status.PUBLISHED)

        limit = int(options["limit"] or 0)
        if limit > 0:
            queryset = queryset[:limit]

        processed = 0
        applied = 0
        disabled = 0

        for post in queryset:
            processed += 1
            result = apply_auto_taxonomy_to_post(post)
            if result.get("applied"):
                applied += 1
            elif result.get("reason") == "disabled":
                disabled += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed={processed} auto_applied={applied} disabled_mode={disabled}"
            )
        )
