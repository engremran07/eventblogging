"""
Comments app services - ALL business logic for comments, reactions, bookmarks.
Services use selectors for queries, perform business operations, emit events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from core.integrations import emit_platform_webhook
from comments.moderation import evaluate_comment_risk
from .models import Comment, PostLike, PostBookmark, NewsletterSubscriber
from . import selectors

if TYPE_CHECKING:
    from blog.models import Post


# ============================================================================
# COMMENT SERVICES
# ============================================================================

def create_comment(
    post: Post,
    author: User,
    body: str,
    *,
    auto_approve: bool | None = None
) -> Comment:
    """
    Create a new comment with moderation check.

    Args:
        post: The Post being commented on
        author: The User creating the comment
        body: Comment text
        auto_approve: Manually set approval status (None = auto-detect)

    Returns:
        Created Comment object

    Raises:
        ValidationError: If comment fails validation
    """
    # Check for duplicates
    if selectors.comment_exists(post, author, body):
        raise ValidationError("This comment was already posted.")

    if len(body.strip()) < 3:
        raise ValidationError("Comment must be at least 3 characters long.")

    if len(body) > 5000:
        raise ValidationError("Comment must be under 5000 characters.")

    # Evaluate moderation risk
    risk_score, risk_reasons = evaluate_comment_risk(body, author, post)

    # Auto-approve based on score and settings
    if auto_approve is not None:
        is_approved = auto_approve
    else:
        is_approved = risk_score < 50  # 50 = threshold for auto-approval

    # Create comment
    comment = Comment.objects.create(
        post=post,
        author=author,
        body=body,
        is_approved=is_approved,
        moderation_score=risk_score,
        moderation_reasons=risk_reasons,
    )

    # Emit webhook event
    emit_platform_webhook("comment.created", {
        "comment_id": comment.id,
        "post_id": post.id,
        "author_id": author.id,
        "approved": is_approved,
    })

    return comment


def approve_comment(comment: Comment) -> Comment:
    """Mark a comment as approved."""
    if comment.is_approved:
        return comment

    comment.is_approved = True
    comment.save(update_fields=["is_approved", "updated_at"])

    emit_platform_webhook("comment.approved", {
        "comment_id": comment.id,
        "post_id": comment.post.id,
    })

    return comment


def reject_comment(comment: Comment) -> Comment:
    """Mark a comment as rejected (not approved)."""
    if not comment.is_approved:
        return comment

    comment.is_approved = False
    comment.save(update_fields=["is_approved", "updated_at"])

    emit_platform_webhook("comment.rejected", {
        "comment_id": comment.id,
        "post_id": comment.post.id,
    })

    return comment


def delete_comment(comment: Comment) -> None:
    """Delete a comment (hard delete)."""
    post_id = comment.post_id
    comment.delete()

    emit_platform_webhook("comment.deleted", {
        "comment_id": comment.id,
        "post_id": post_id,
    })


def bulk_approve_comments(comment_ids: list[int]) -> int:
    """Bulk approve comments by IDs."""
    count = (
        Comment.objects
        .filter(id__in=comment_ids, is_approved=False)
        .update(is_approved=True, updated_at=timezone.now())
    )
    return count


# ============================================================================
# LIKE/REACTION SERVICES
# ============================================================================

def toggle_post_like(post: Post, user: User) -> tuple[bool, str]:
    """
    Toggle like status for a post.

    Returns:
        (is_liked_after, action) where action is "liked" or "unliked"
    """
    try:
        like = PostLike.objects.get(post=post, user=user)
        like.delete()
        action = "unliked"
        is_liked = False
    except PostLike.DoesNotExist:
        PostLike.objects.create(post=post, user=user)
        action = "liked"
        is_liked = True

    emit_platform_webhook(f"post.{action}", {
        "post_id": post.id,
        "user_id": user.id,
    })

    return is_liked, action


# ============================================================================
# BOOKMARK SERVICES
# ============================================================================

def toggle_post_bookmark(post: Post, user: User) -> tuple[bool, str]:
    """
    Toggle bookmark status for a post.

    Returns:
        (is_bookmarked_after, action) where action is "bookmarked" or "unbookmarked"
    """
    try:
        bookmark = PostBookmark.objects.get(post=post, user=user)
        bookmark.delete()
        action = "unbookmarked"
        is_bookmarked = False
    except PostBookmark.DoesNotExist:
        PostBookmark.objects.create(post=post, user=user)
        action = "bookmarked"
        is_bookmarked = True

    emit_platform_webhook(f"post.{action}", {
        "post_id": post.id,
        "user_id": user.id,
    })

    return is_bookmarked, action


# ============================================================================
# NEWSLETTER SERVICES
# ============================================================================

def subscribe_to_newsletter(email: str) -> tuple[NewsletterSubscriber, bool]:
    """
    Subscribe an email to the newsletter.

    Returns:
        (subscriber_object, was_created)
    """
    if not email or "@" not in email:
        raise ValidationError("Invalid email address.")

    subscriber, created = NewsletterSubscriber.objects.get_or_create(
        email=email.lower().strip(),
        defaults={"is_active": True}
    )

    if not created and not subscriber.is_active:
        subscriber.is_active = True
        subscriber.save(update_fields=["is_active"])

    emit_platform_webhook("newsletter.subscribed", {
        "email": email,
        "is_new": created,
    })

    return subscriber, created


def unsubscribe_from_newsletter(email: str) -> bool:
    """
    Unsubscribe an email from the newsletter.

    Returns:
        True if subscriber was found and deactivated, False otherwise
    """
    try:
        subscriber = NewsletterSubscriber.objects.get(email=email.lower().strip())
        if subscriber.is_active:
            subscriber.is_active = False
            subscriber.save(update_fields=["is_active"])

            emit_platform_webhook("newsletter.unsubscribed", {
                "email": email,
            })

            return True
        return False
    except NewsletterSubscriber.DoesNotExist:
        return False


def bulk_subscribe_newsletter(emails: list[str]) -> dict[str, int | list[str]]:
    """
    Bulk subscribe emails to newsletter.

    Returns:
        {
            "created": int,
            "existing": int,
            "invalid": list[str],
        }
    """
    created_count = 0
    existing_count = 0
    invalid = []

    for email in emails:
        try:
            _, was_created = subscribe_to_newsletter(email)
            if was_created:
                created_count += 1
            else:
                existing_count += 1
        except ValidationError:
            invalid.append(email)

    return {
        "created": created_count,
        "existing": existing_count,
        "invalid": invalid,
    }


# ============================================================================
# BATCH OPERATIONS
# ============================================================================

@transaction.atomic
def delete_user_comments(user: User) -> int:
    """
    Delete all comments by a user (hard delete).
    Used when user account is deleted.
    """
    comments = Comment.objects.filter(author=user)
    count, _ = comments.delete()
    return count


@transaction.atomic
def delete_post_comments(post: Post) -> int:
    """
    Delete all comments on a post (hard delete).
    Used when post is permanently deleted.
    """
    comments = Comment.objects.filter(post=post)
    count, _ = comments.delete()
    return count
