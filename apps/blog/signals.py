"""
Blog app signals.

Wires post-save hooks for:
- Emitting platform webhooks when a Post transitions to PUBLISHED status.
- Triggering comment moderation immediately after a Comment is saved.

All signal handlers are registered in BlogConfig.ready() via the standard
Django ready() hook (see apps.py).  Import *only* this module from ready().
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _previous_status(instance: Any) -> str | None:
    """
    Return the status value that was stored *before* the current save by
    querying the database.  Returns None when the row did not exist yet
    (i.e. on INSERT).
    """
    from .models import Post

    if not instance.pk:
        return None
    try:
        return Post.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    except Exception:
        logger.warning(
            "blog.signals: could not read previous status for post pk=%s",
            instance.pk,
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Post signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender="blog.Post")
def emit_webhook_on_publish(sender: type[Any], instance: Any, created: bool, raw: bool, **kwargs: Any) -> None:
    """
    Fire a platform webhook when a Post transitions to PUBLISHED for the first
    time.  Runs on commit so the row is visible to any background worker.

    Skipped when:
    - raw=True (fixture loading / test data)
    - Post is not in PUBLISHED status
    - A _seo_skip_signal flag is set (internal re-save loop)
    """
    if raw or getattr(instance, "_seo_skip_signal", False):
        return

    from .models import Post

    if instance.status != Post.Status.PUBLISHED.value:  # type: ignore[comparison-overlap]
        return

    # Guard: emit only when this save represents the PUBLISHED transition.
    # On INSERT (created=True) we know there was no previous status.
    # On UPDATE we compare against the DB state that existed before this save.
    if not created:
        previous = _previous_status(instance)
        if previous == Post.Status.PUBLISHED.value:  # type: ignore[comparison-overlap]
            # Already was published before this save — skip to avoid duplicate
            # webhooks on every subsequent update to a published post.
            return

    post_pk = int(instance.pk)

    def _fire():
        try:
            from core.integrations import emit_platform_webhook

            emit_platform_webhook(
                event="post.published",
                payload={
                    "post_id": post_pk,
                    "title": instance.title,
                    "slug": instance.slug,
                    "url": instance.get_absolute_url(),
                },
            )
        except Exception:
            logger.warning(
                "blog.signals: webhook failed for post pk=%s",
                post_pk,
                exc_info=True,
            )

    from django.db import transaction

    transaction.on_commit(_fire)


# ---------------------------------------------------------------------------
# Comment signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender="comments.Comment")
def trigger_comment_moderation(sender: type[Any], instance: Any, created: bool, raw: bool, **kwargs: Any) -> None:
    """
    Re-run moderation scoring on freshly created comments when the
    ``moderate_comments`` feature flag is enabled.

    On creation, ``services.create_comment`` already calls moderation before
    the first save.  This signal acts as a backstop for comments inserted via
    Django admin, fixtures, or management commands that bypass the service.

    Only fires on INSERT (created=True) to avoid re-scoring edits.
    """
    if raw or not created:
        return

    try:
        from core.utils import cache_feature_control_settings

        controls = cache_feature_control_settings()
        if not getattr(controls, "moderate_comments", False):
            return
    except Exception:
        logger.warning(
            "blog.signals: could not read FeatureControlSettings; skipping moderation hook",
            exc_info=True,
        )
        return

    # Skip if the comment already has a moderation score (set by service layer)
    if getattr(instance, "moderation_score", None) is not None and instance.moderation_score > 0:
        return

    try:
        from comments.moderation import evaluate_comment_risk

        result = evaluate_comment_risk(instance.body)
        score = int(result.get("score", 0))  # type: ignore[arg-type]
        reasons = result.get("reasons", [])
        threshold = int(getattr(controls, "comment_spam_threshold", 50))  # type: ignore[arg-type]

        # If score is high enough to warrant rejection, flip approval state
        if score >= threshold and instance.is_approved:
            type(instance).objects.filter(pk=instance.pk).update(  # type: ignore[union-attr]
                is_approved=False,
                moderation_score=score,
                moderation_reasons=reasons,
            )
            logger.warning(
                "blog.signals: comment pk=%s auto-rejected via backstop moderation "
                "(score=%s, threshold=%s)",
                instance.pk,
                score,
                threshold,
            )
    except Exception:
        logger.warning(
            "blog.signals: backstop moderation failed for comment pk=%s",
            instance.pk,
            exc_info=True,
        )
