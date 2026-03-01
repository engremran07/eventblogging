"""
Comments app database query selectors - ALL data access goes here.
No business logic, only ORM queries with proper optimization.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from blog.models import Post

from .models import Comment, NewsletterSubscriber, PostBookmark, PostLike, PostView

# ============================================================================
# COMMENT SELECTORS
# ============================================================================

def get_comment(comment_id: int) -> Comment:
    """Get a comment by ID."""
    return get_object_or_404(
        Comment.objects.select_related("post", "author"),
        id=comment_id,
    )


def get_post_comments(post: Post, approved_only: bool = True) -> QuerySet[Comment]:
    """Get comments for a post, optionally filtering for approved only."""
    qs = (
        Comment.objects
        .filter(post=post)
        .select_related("author")
        .order_by("created_at")
    )
    if approved_only:
        qs = qs.filter(is_approved=True)
    return qs


def get_post_comments_count(post: Post, approved_only: bool = True) -> int:
    """Get comment count for a post (optimized single query)."""
    qs = Comment.objects.filter(post=post)
    if approved_only:
        qs = qs.filter(is_approved=True)
    return qs.count()


def get_comments_pending_moderation() -> QuerySet[Comment]:
    """Get all comments awaiting moderation."""
    return (
        Comment.objects
        .filter(is_approved=False)
        .select_related("post", "author")
        .order_by("created_at")
    )


def get_user_comments(user: User) -> QuerySet[Comment]:
    """Get all comments by a specific user."""
    return (
        Comment.objects
        .filter(author=user)
        .select_related("post")
        .order_by("-created_at")
    )


def comment_exists(post: Post, author: User, body: str) -> bool:
    """Check if identical comment already exists (prevent duplicates)."""
    return Comment.objects.filter(
        post=post,
        author=author,
        body=body
    ).exists()


# ============================================================================
# LIKE/REACTION SELECTORS
# ============================================================================

def user_liked_post(post: Post, user: User) -> bool:
    """Check if user has liked a post."""
    if not user.is_authenticated:
        return False
    return PostLike.objects.filter(post=post, user=user).exists()


def get_post_likes(post: Post) -> QuerySet[PostLike]:
    """Get all likes for a post."""
    return PostLike.objects.filter(post=post).select_related("user")


def get_post_likes_count(post: Post) -> int:
    """Get like count for a post (optimized single query)."""
    return PostLike.objects.filter(post=post).count()


def get_user_liked_posts(user: User) -> QuerySet[Post]:
    """Get all posts liked by a user."""
    return (
        Post.objects
        .filter(likes__user=user)
        .distinct()
        .select_related("author")
    )


def user_likes_or_bookmarks_post(post: Post, user: User) -> dict[str, bool]:
    """Check both like and bookmark status in single query."""
    if not user.is_authenticated:
        return {"liked": False, "bookmarked": False}

    return {
        "liked": PostLike.objects.filter(post=post, user=user).exists(),
        "bookmarked": PostBookmark.objects.filter(post=post, user=user).exists(),
    }


# ============================================================================
# BOOKMARK SELECTORS
# ============================================================================

def user_bookmarked_post(post: Post, user: User) -> bool:
    """Check if user has bookmarked a post."""
    if not user.is_authenticated:
        return False
    return PostBookmark.objects.filter(post=post, user=user).exists()


def get_post_bookmarks(post: Post) -> QuerySet[PostBookmark]:
    """Get all bookmarks for a post."""
    return PostBookmark.objects.filter(post=post).select_related("user")


def get_post_bookmarks_count(post: Post) -> int:
    """Get bookmark count for a post (optimized single query)."""
    return PostBookmark.objects.filter(post=post).count()


def get_user_bookmarked_posts(user: User) -> QuerySet[Post]:
    """Get all posts bookmarked by a user."""
    return (
        Post.objects
        .filter(bookmarks__user=user)
        .distinct()
        .select_related("author")
    )


# ============================================================================
# VIEW TRACKING SELECTORS
# ============================================================================

def get_post_views(post: Post) -> QuerySet[PostView]:
    """Get all view events for a post."""
    return PostView.objects.filter(post=post).select_related("user")


def get_post_views_count(post: Post) -> int:
    """Get view count for a post (optimized single query)."""
    return PostView.objects.filter(post=post).count()


def get_user_post_views(user: User) -> QuerySet[PostView]:
    """Get all view events by a user."""
    return PostView.objects.filter(user=user).select_related("post")


# ============================================================================
# COMBINED REACTION DATA (for views/templates)
# ============================================================================

def get_post_reaction_counts(post: Post) -> dict[str, int]:
    """
    Get all reaction counts for a post.

    NOTE: For efficient processing of multiple posts, use annotations instead:
    Post.objects.all().with_reaction_counts()

    This is optimized for single-post detail views.
    """
    return {
        "like_total": get_post_likes_count(post),
        "bookmark_total": get_post_bookmarks_count(post),
        "comment_total": get_post_comments_count(post),
    }


# ============================================================================
# NEWSLETTER SELECTORS
# ============================================================================

def get_newsletter_subscriber(email: str) -> NewsletterSubscriber | None:
    """Get newsletter subscriber by email."""
    try:
        return NewsletterSubscriber.objects.get(email=email)
    except NewsletterSubscriber.DoesNotExist:
        return None


def newsletter_subscriber_exists(email: str) -> bool:
    """Check if email is subscribed to newsletter."""
    return NewsletterSubscriber.objects.filter(email=email, is_active=True).exists()


def get_active_newsletter_subscribers() -> QuerySet[NewsletterSubscriber]:
    """Get all active newsletter subscribers."""
    return NewsletterSubscriber.objects.filter(is_active=True).order_by("-created_at")


def get_newsletter_subscribers_count() -> int:
    """Get count of active newsletter subscribers."""
    return NewsletterSubscriber.objects.filter(is_active=True).count()


def bulk_subscribe_newsletter(emails: list[str]) -> tuple[int, list[str]]:
    """
    Bulk subscribe emails to newsletter.
    Returns: (newly_created_count, existing_emails)
    """
    existing = set(
        NewsletterSubscriber.objects
        .filter(email__in=emails, is_active=True)
        .values_list("email", flat=True)
    )

    new_emails = [e for e in emails if e not in existing]

    if new_emails:
        NewsletterSubscriber.objects.bulk_create(
            [NewsletterSubscriber(email=email) for email in new_emails],
            ignore_conflicts=True
        )

    return len(new_emails), list(existing)
