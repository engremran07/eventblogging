from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from pages.models import Page

from .models import ContentRefreshSettings, Post


def _refresh_queryset(queryset, cutoff, now, max_items, force=False):
    if not force:
        queryset = queryset.filter(updated_at__lt=cutoff)
    target_ids = list(queryset.order_by("updated_at").values_list("id", flat=True)[:max_items])
    if not target_ids:
        return 0
    return queryset.model.objects.filter(id__in=target_ids).update(updated_at=now)


def run_content_date_refresh(force=False, now=None):
    now = now or timezone.now()
    settings = ContentRefreshSettings.get_solo()

    if not force and not settings.auto_refresh_enabled:
        return {
            "posts_updated": 0,
            "pages_updated": 0,
            "ran": False,
            "reason": "auto_refresh_disabled",
        }

    post_cutoff = now - timedelta(hours=max(settings.post_refresh_interval_hours, 1))
    page_cutoff = now - timedelta(hours=max(settings.page_refresh_interval_hours, 1))
    max_items = max(settings.max_items_per_run, 1)

    posts_updated = _refresh_queryset(
        Post.objects.published(),
        post_cutoff,
        now,
        max_items,
        force=force,
    )
    pages_updated = _refresh_queryset(
        Page.objects.published(),
        page_cutoff,
        now,
        max_items,
        force=force,
    )

    settings.last_run_at = now
    settings.save(update_fields=["last_run_at", "updated_at"])

    return {
        "posts_updated": posts_updated,
        "pages_updated": pages_updated,
        "ran": True,
        "reason": "ok",
    }
