"""
Management command: seo_backfill

Retroactively runs the full SEO signal pipeline on all existing posts and pages:
  - Auto metadata (meta_title, meta_description, schema_markup, internal links)
  - Content signals (Flesch score, keyword density, heading/image counts)
  - TF-IDF keyword extraction
  - Audit snapshot + score write-back
  - Reverse interlink scan (published content only)
  - Orphan repair (ensures every published item has inbound links)

Usage:
    python manage.py seo_backfill
    python manage.py seo_backfill --batch-size 25  # smaller batches
    python manage.py seo_backfill --posts-only
    python manage.py seo_backfill --pages-only
    python manage.py seo_backfill --repair-orphans  # only run orphan repair pass
"""
from __future__ import annotations

import logging
import time

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the full SEO signal pipeline on all existing posts and pages."

    def add_arguments(self, parser):  # type: ignore[override]
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of items to process per batch (default: 50).",
        )
        parser.add_argument(
            "--posts-only",
            action="store_true",
            default=False,
            help="Only backfill posts.",
        )
        parser.add_argument(
            "--pages-only",
            action="store_true",
            default=False,
            help="Only backfill pages.",
        )
        parser.add_argument(
            "--repair-orphans",
            action="store_true",
            default=False,
            help="Only run the orphan repair pass (skip full pipeline).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be processed without writing anything.",
        )

    def handle(self, **options):  # type: ignore[override]
        batch_size: int = max(1, min(options["batch_size"], 500))
        posts_only: bool = options["posts_only"]
        pages_only: bool = options["pages_only"]
        repair_only: bool = options["repair_orphans"]
        dry_run: bool = options["dry_run"]

        if repair_only:
            self._repair_orphans(dry_run=dry_run)
            return

        if not pages_only:
            self._backfill_posts(batch_size=batch_size, dry_run=dry_run)

        if not posts_only:
            self._backfill_pages(batch_size=batch_size, dry_run=dry_run)

        # After all content is processed, run orphan repair
        if not dry_run:
            self._repair_orphans(dry_run=False)

        self.stdout.write(self.style.SUCCESS("SEO backfill complete."))

    def _backfill_posts(self, *, batch_size: int, dry_run: bool) -> None:
        from blog.models import Post

        total = Post.objects.count()
        self.stdout.write(f"Backfilling {total} posts (batch_size={batch_size})...")
        if dry_run:
            self.stdout.write(self.style.WARNING(f"  DRY RUN — would process {total} posts"))
            return

        processed = 0
        errors = 0
        start = time.monotonic()
        for post in Post.objects.order_by("id").iterator(chunk_size=batch_size):
            try:
                self._run_post_pipeline(post)
                processed += 1
            except Exception:
                errors += 1
                logger.exception("Backfill failed for Post id=%s", post.pk)
            if processed % batch_size == 0:
                elapsed = time.monotonic() - start
                self.stdout.write(f"  Posts: {processed}/{total} ({elapsed:.1f}s, {errors} errors)")

        elapsed = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(f"  Posts done: {processed}/{total} in {elapsed:.1f}s ({errors} errors)")
        )

    def _backfill_pages(self, *, batch_size: int, dry_run: bool) -> None:
        from pages.models import Page

        total = Page.objects.count()
        self.stdout.write(f"Backfilling {total} pages (batch_size={batch_size})...")
        if dry_run:
            self.stdout.write(self.style.WARNING(f"  DRY RUN — would process {total} pages"))
            return

        processed = 0
        errors = 0
        start = time.monotonic()
        for page in Page.objects.order_by("id").iterator(chunk_size=batch_size):
            try:
                self._run_page_pipeline(page)
                processed += 1
            except Exception:
                errors += 1
                logger.exception("Backfill failed for Page id=%s", page.pk)
            if processed % batch_size == 0:
                elapsed = time.monotonic() - start
                self.stdout.write(f"  Pages: {processed}/{total} ({elapsed:.1f}s, {errors} errors)")

        elapsed = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(f"  Pages done: {processed}/{total} in {elapsed:.1f}s ({errors} errors)")
        )

    def _run_post_pipeline(self, post) -> None:
        """Run the full signal pipeline for a single post."""
        from seo.interlink import reverse_interlink_scan
        from seo.services import (
            audit_instance,
            compute_content_signals,
            compute_tfidf_signals,
            write_back_audit_score,
        )
        from seo.signals import _apply_auto_seo_enhancements

        _apply_auto_seo_enhancements(post)

        snapshot = audit_instance(post, trigger="backfill")

        compute_content_signals(post)
        compute_tfidf_signals(post)

        if snapshot:
            write_back_audit_score(post, snapshot)

        if post.status == post.Status.PUBLISHED:
            reverse_interlink_scan(post)

    def _run_page_pipeline(self, page) -> None:
        """Run the full signal pipeline for a single page."""
        from seo.interlink import reverse_interlink_scan
        from seo.services import (
            audit_instance,
            compute_content_signals,
            write_back_audit_score,
        )
        from seo.signals import _apply_page_metadata

        _apply_page_metadata(page)

        snapshot = audit_instance(page, trigger="backfill")

        compute_content_signals(page)

        if snapshot:
            write_back_audit_score(page, snapshot)

        if getattr(page, "status", "") == "published":
            reverse_interlink_scan(page)

    def _repair_orphans(self, *, dry_run: bool) -> None:
        """Find and repair orphaned content (no inbound interlinks)."""
        from seo.interlink import find_orphan_content, repair_orphans

        self.stdout.write("Checking for orphaned content...")
        orphans = find_orphan_content()
        orphan_posts = orphans.get("posts", [])
        orphan_pages = orphans.get("pages", [])
        total = len(orphan_posts) + len(orphan_pages)
        if not total:
            self.stdout.write(self.style.SUCCESS("  No orphans found."))
            return

        self.stdout.write(f"  Found {total} orphaned items ({len(orphan_posts)} posts, {len(orphan_pages)} pages).")
        if dry_run:
            for pk in orphan_posts[:10]:
                self.stdout.write(f"    - Post pk={pk}")
            for pk in orphan_pages[:10]:
                self.stdout.write(f"    - Page pk={pk}")
            if total > 20:
                self.stdout.write(f"    ... and {total - 20} more")
            return

        result = repair_orphans()
        self.stdout.write(self.style.SUCCESS(
            f"  Repaired {result.get('repairs_created', 0)} orphans."
        ))
