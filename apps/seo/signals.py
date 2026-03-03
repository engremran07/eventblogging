from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from blog.models import Post
from blog.services import apply_auto_taxonomy_to_post
from pages.models import Page

from .models import TaxonomySynonymGroup, TaxonomySynonymTerm
from .services import (
    audit_instance,
    compute_content_signals,
    compute_tfidf_signals,
    disable_gone_redirect_for_live_instance,
    handle_deleted_content,
    run_autopilot_for_instance,
    write_back_audit_score,
)
from .synonyms import clear_synonym_cache

logger = logging.getLogger(__name__)
_last_change_scan_queued_at = None

# Cache key prefix used by SeoRedirectMiddleware — must stay in sync with middleware.
_REDIRECT_CACHE_PREFIX = "seo_redirect_rule_v1"


def _should_skip(instance, raw: bool):
    return raw or bool(getattr(instance, "_seo_skip_signal", False)) or not getattr(instance, "pk", None)


def _log_metadata_changes(instance: Any, changes: dict[str, str]) -> None:
    """Log autonomous metadata changes to SeoChangeLog for admin visibility."""
    try:
        from django.contrib.contenttypes.models import ContentType

        from .models import SeoChangeLog
        ct = ContentType.objects.get_for_model(instance.__class__)
        rows = []
        for field_name, old_value in changes.items():
            new_value = str(getattr(instance, field_name, "") or "")
            if field_name == "meta_title":
                change_type = SeoChangeLog.ChangeType.META_TITLE_FIXED
            elif field_name == "meta_description":
                change_type = SeoChangeLog.ChangeType.META_DESC_FIXED
            elif field_name == "canonical_url" and old_value:
                change_type = SeoChangeLog.ChangeType.CANONICAL_FIXED
            elif field_name == "canonical_url":
                change_type = SeoChangeLog.ChangeType.CANONICAL_SET
            else:
                change_type = SeoChangeLog.ChangeType.METADATA_APPROVED
            rows.append(SeoChangeLog(
                content_type=ct,
                object_id=instance.pk,
                change_type=change_type,
                field_name=field_name,
                old_value=str(old_value),
                new_value=new_value,
            ))
        if rows:
            SeoChangeLog.objects.bulk_create(rows)
    except Exception:
        logger.warning("Failed to log SEO metadata changes", exc_info=True)


def _apply_auto_seo_enhancements(post: Post) -> None:
    from .interlink import suggest_internal_links
    from .metadata import apply_auto_metadata_to_instance, generate_schema_markup

    changed_fields = set()
    post._seo_skip_signal = True
    try:
        try:
            apply_auto_taxonomy_to_post(post)
        except Exception:
            logger.exception("Auto taxonomy failed for post id=%s", post.pk)

        previous_meta_title = post.meta_title
        previous_meta_description = post.meta_description
        previous_canonical = getattr(post, "canonical_url", "") or ""
        metadata_changes = apply_auto_metadata_to_instance(post)
        if post.meta_title != previous_meta_title:
            changed_fields.add("meta_title")
        if post.meta_description != previous_meta_description:
            changed_fields.add("meta_description")
        if getattr(post, "canonical_url", "") != previous_canonical:
            changed_fields.add("canonical_url")

        # Log autonomous metadata changes
        if metadata_changes:
            _log_metadata_changes(post, metadata_changes)

        schema_markup = generate_schema_markup(
            post,
            post.canonical_url or post.get_absolute_url(),
            schema_type="BlogPosting",
        )
        if post.schema_markup != schema_markup:
            post.schema_markup = schema_markup
            changed_fields.add("schema_markup")

        internal_link_suggestions = []
        if post.status == Post.Status.PUBLISHED:
            try:
                internal_link_suggestions = suggest_internal_links(post)
            except Exception:
                logger.exception("Internal-link suggestion failed for post id=%s", post.pk)
        if post.suggested_internal_links != internal_link_suggestions:
            post.suggested_internal_links = internal_link_suggestions
            changed_fields.add("suggested_internal_links")

        if changed_fields:
            post.save(update_fields=[*sorted(changed_fields), "updated_at"])
    finally:
        post._seo_skip_signal = False


def _apply_page_metadata(page: Page) -> None:
    """
    Keep page metadata populated through the same centralized metadata policy.
    """
    from .metadata import apply_auto_metadata_to_instance

    before_title = page.meta_title
    before_description = page.meta_description
    before_canonical = getattr(page, "canonical_url", "") or ""
    metadata_changes = apply_auto_metadata_to_instance(page)
    changed_fields = []
    if page.meta_title != before_title:
        changed_fields.append("meta_title")
    if page.meta_description != before_description:
        changed_fields.append("meta_description")
    if getattr(page, "canonical_url", "") != before_canonical:
        changed_fields.append("canonical_url")

    # Log autonomous metadata changes
    if metadata_changes:
        _log_metadata_changes(page, metadata_changes)

    if not changed_fields:
        return
    page._seo_skip_signal = True
    try:
        page.save(update_fields=[*changed_fields, "updated_at"])
    finally:
        page._seo_skip_signal = False


def _run_post_save_pipeline(post_id: int, *, trigger: str = "save") -> None:
    post = Post.objects.filter(pk=post_id).first()
    if not post:
        return
    try:
        _apply_auto_seo_enhancements(post)
    except Exception:
        logger.exception("Post SEO enhancement failed for post id=%s", post_id)
    try:
        snapshot = audit_instance(post, trigger=trigger)
    except Exception:
        logger.exception("SEO audit failed for post id=%s", post_id)
        snapshot = None
    # Compute content signals (Flesch, keyword density, heading/image counts, etc.)
    try:
        compute_content_signals(post)
    except Exception:
        logger.exception("Content signal computation failed for post id=%s", post_id)
    # TF-IDF keyword extraction
    try:
        compute_tfidf_signals(post)
    except Exception:
        logger.exception("TF-IDF signal computation failed for post id=%s", post_id)
    # Write audit score back to model
    if snapshot:
        try:
            write_back_audit_score(post, snapshot)
        except Exception:
            logger.exception("Audit score write-back failed for post id=%s", post_id)
    # Reverse interlink scan — ensure bidirectional crawl paths
    if post.status == Post.Status.PUBLISHED:
        try:
            from .interlink import reverse_interlink_scan
            reverse_interlink_scan(post)
        except Exception:
            logger.exception("Reverse interlink scan failed for post id=%s", post_id)
    try:
        run_autopilot_for_instance(post)
    except Exception:
        logger.exception("SEO autopilot failed for post id=%s", post_id)


def _run_page_save_pipeline(page_id: int, *, trigger: str = "save") -> None:
    page = Page.objects.filter(pk=page_id).first()
    if not page:
        return
    try:
        _apply_page_metadata(page)
    except Exception:
        logger.exception("Page metadata enhancement failed for page id=%s", page_id)
    try:
        snapshot = audit_instance(page, trigger=trigger)
    except Exception:
        logger.exception("SEO audit failed for page id=%s", page_id)
        snapshot = None
    # Compute content signals (Flesch, keyword density, heading/image counts, etc.)
    try:
        compute_content_signals(page)
    except Exception:
        logger.exception("Content signal computation failed for page id=%s", page_id)
    # Write audit score back to model
    if snapshot:
        try:
            write_back_audit_score(page, snapshot)
        except Exception:
            logger.exception("Audit score write-back failed for page id=%s", page_id)
    # Reverse interlink scan — ensure bidirectional crawl paths
    if getattr(page, 'status', '') == 'published':
        try:
            from .interlink import reverse_interlink_scan
            reverse_interlink_scan(page)
        except Exception:
            logger.exception("Reverse interlink scan failed for page id=%s", page_id)
    try:
        run_autopilot_for_instance(page)
    except Exception:
        logger.exception("SEO autopilot failed for page id=%s", page_id)


def _queue_change_scan(reason: str) -> None:
    """
    Queue a changed-content scan so delete events refresh interlink state.
    """
    global _last_change_scan_queued_at
    now = timezone.now()
    if _last_change_scan_queued_at and (
        now - _last_change_scan_queued_at
    ).total_seconds() < 5:
        return

    try:
        from .admin_config_services import create_scan_job, enqueue_scan_job
        from .models import SeoEngineSettings, SeoScanJob

        settings = SeoEngineSettings.get_solo()
        if not settings.enable_checks:
            return

        _last_change_scan_queued_at = now
        job = create_scan_job(
            job_type=SeoScanJob.JobType.CHANGED_ONLY,
            started_by=None,
            trigger=SeoScanJob.Trigger.SCHEDULED,
            notes=f"Auto change scan after {reason}.",
        )
        enqueue_scan_job(job.id)
    except Exception:
        logger.exception("Unable to queue SEO change scan for reason=%s", reason)


@receiver(post_save, sender=Post)
def audit_post_on_save(sender, instance: Post, created, raw, **kwargs):
    if _should_skip(instance, raw):
        return
    disable_gone_redirect_for_live_instance(instance)
    post_id = int(instance.pk)
    trigger = "save"
    transaction.on_commit(lambda: _run_post_save_pipeline(post_id, trigger=trigger))


@receiver(post_save, sender=Page)
def audit_page_on_save(sender, instance: Page, created, raw, **kwargs):
    if _should_skip(instance, raw):
        return
    disable_gone_redirect_for_live_instance(instance)
    page_id = int(instance.pk)
    trigger = "save"
    transaction.on_commit(lambda: _run_page_save_pipeline(page_id, trigger=trigger))


@receiver(post_delete, sender=Post)
def create_post_redirect_suggestion(sender, instance: Post, **kwargs):
    handle_deleted_content(instance)
    transaction.on_commit(lambda: _queue_change_scan("post deletion"))


@receiver(post_delete, sender=Page)
def create_page_redirect_suggestion(sender, instance: Page, **kwargs):
    handle_deleted_content(instance)
    transaction.on_commit(lambda: _queue_change_scan("page deletion"))


@receiver(post_save, sender=TaxonomySynonymGroup)
@receiver(post_delete, sender=TaxonomySynonymGroup)
@receiver(post_save, sender=TaxonomySynonymTerm)
@receiver(post_delete, sender=TaxonomySynonymTerm)
def invalidate_synonym_cache(**kwargs):
    clear_synonym_cache()


# ---------------------------------------------------------------------------
# Redirect rule signals — keep the SeoRedirectMiddleware cache consistent
# ---------------------------------------------------------------------------

from .models import SeoRedirectRule  # noqa: E402 — imported after module-level setup


@receiver(post_save, sender=SeoRedirectRule)
@receiver(post_delete, sender=SeoRedirectRule)
def invalidate_redirect_cache(sender, instance, **kwargs) -> None:
    """
    Purge the per-path redirect cache entry whenever a redirect rule is
    created, updated, or deleted.  The middleware sets keys as:
    ``{_REDIRECT_CACHE_PREFIX}:{old_path}``
    """
    from django.core.cache import cache

    old_path = getattr(instance, "old_path", None)
    if old_path:
        cache.delete(f"{_REDIRECT_CACHE_PREFIX}:{old_path}")
        logger.debug(
            "seo.signals: redirect cache purged for path=%s", old_path
        )
