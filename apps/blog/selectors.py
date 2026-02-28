from __future__ import annotations

from typing import TYPE_CHECKING, cast
from django.db.models import Q, Count, Avg, QuerySet
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils import timezone
from django.contrib.auth.models import User

from comments.models import Comment, PostLike, PostBookmark, PostView
from .models import Post

if TYPE_CHECKING:
    pass


# ============================================================================
# POST SELECTORS
# ============================================================================

def get_post_by_slug(slug: str, user: User | None = None) -> Post:
    """
    Get a post by slug with all related data pre-fetched.
    Checks visibility based on user authentication and post status.
    """
    post = get_object_or_404(
        Post.objects.select_related("author", "primary_topic").prefetch_related(
            "tags",
            "categories",
            "comments__author",
        ),
        slug=slug,
    )
    
    # Check if user can access this post
    if user and user.is_authenticated and user == post.author:
        return post
    
    if (post.status == Post.Status.PUBLISHED 
        and post.published_at is not None 
        and post.published_at <= timezone.now()):
        return post
    
    raise Http404("Post not available")


def get_published_posts() -> QuerySet[Post]:
    """Get all published posts ordered by publication date (newest first)."""
    return (
        Post.objects.filter(
            status=Post.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )
        .select_related("author", "primary_topic")
        .prefetch_related("tags", "categories")
        .with_reaction_counts()
        .order_by("-published_at")
    )


def get_user_posts(user: User) -> QuerySet[Post]:
    """Get all posts for a specific user with reaction counts."""
    return (
        Post.objects.filter(author=user)
        .select_related("author", "primary_topic")
        .prefetch_related("tags", "categories")
        .with_reaction_counts()
        .order_by("-updated_at")
    )


def get_admin_posts(
    search: str = "", 
    status: str = "", 
    category: str = "", 
    sort: str = "-published_at"
) -> QuerySet[Post]:
    """Get posts for admin list with filters."""
    posts = Post.objects.select_related("author").prefetch_related("categories", "tags")
    
    valid_statuses = {choice[0] for choice in Post.Status.choices}
    
    if status in valid_statuses:
        posts = posts.filter(status=status)
    
    if category:
        posts = posts.filter(categories__name__icontains=category)
    
    if search:
        posts = posts.filter(
            Q(title__icontains=search)
            | Q(slug__icontains=search)
            | Q(tags__name__icontains=search)
        ).distinct()
    
    valid_sorts = ["-published_at", "published_at", "-updated_at", "updated_at", "title", "-title"]
    if sort not in valid_sorts:
        sort = "-published_at"
    
    return posts.order_by(sort)


def get_posts_by_tag(tag_name: str) -> QuerySet[Post]:
    """Get all published posts for a specific tag."""
    return get_published_posts().filter(tags__name__iexact=tag_name)


def get_posts_by_topic(topic_name: str) -> QuerySet[Post]:
    """Get all published posts for a specific topic."""
    return get_published_posts().filter(primary_topic__name__iexact=topic_name)


def get_posts_by_category(category_name: str) -> QuerySet[Post]:
    """Get all published posts for a specific category."""
    return get_published_posts().filter(categories__name__icontains=category_name)


def search_posts(query: str) -> QuerySet[Post]:
    """Search posts by title, subtitle, excerpt, and body."""
    clean_query = (query or "").strip()
    if not clean_query:
        return Post.objects.none()
    
    return get_published_posts().filter(
        Q(title__icontains=clean_query)
        | Q(subtitle__icontains=clean_query)
        | Q(excerpt__icontains=clean_query)
        | Q(body_markdown__icontains=clean_query)
    )


def get_editor_picks() -> QuerySet[Post]:
    """Get all editor pick posts."""
    return get_published_posts().filter(is_editors_pick=True)


# ============================================================================
# COMMENT SELECTORS
# ============================================================================

def get_post_comments(post: Post, user: User | None = None) -> QuerySet[Comment]:
    """
    Get comments for a post.
    If user is post author or staff, returns all comments.
    Otherwise, returns only approved comments.
    """
    comments = cast(QuerySet[Comment], post.comments.select_related("author"))  # type: ignore[attr-defined]
    
    is_post_author = user and user.is_authenticated and user == post.author
    is_staff = user and user.is_staff
    
    if is_post_author or is_staff:
        return comments
    
    return comments.filter(is_approved=True)


def get_admin_comments(search: str = "", status: str = "") -> QuerySet[Comment]:
    """Get comments for admin with filters."""
    comments = Comment.objects.select_related("post", "author")
    
    if status == "pending":
        comments = comments.filter(is_approved=False)
    elif status == "approved":
        comments = comments.filter(is_approved=True)
    
    if search:
        comments = comments.filter(
            Q(author__username__icontains=search)
            | Q(post__title__icontains=search)
            | Q(body__icontains=search)
        )
    
    return comments.order_by("-created_at")


# ============================================================================
# REACTION SELECTORS
# ============================================================================

def get_post_likes(post: Post) -> QuerySet[PostLike]:
    """Get all likes for a post."""
    return PostLike.objects.filter(post=post).select_related("user")


def has_user_liked_post(post: Post, user: User) -> bool:
    """Check if user has liked a post."""
    if not user or not user.is_authenticated:
        return False
    return PostLike.objects.filter(post=post, user=user).exists()


def has_user_bookmarked_post(post: Post, user: User) -> bool:
    """Check if user has bookmarked a post."""
    if not user or not user.is_authenticated:
        return False
    return PostBookmark.objects.filter(post=post, user=user).exists()


def get_user_reaction_state(post: Post, user: User | None = None) -> dict[str, bool]:
    """Get reaction state (likes/bookmarks) for a post and user."""
    if not user or not user.is_authenticated:
        return {"liked": False, "bookmarked": False}
    
    return {
        "liked": has_user_liked_post(post, user),
        "bookmarked": has_user_bookmarked_post(post, user),
    }


# ============================================================================
# DASHBOARD & STATS SELECTORS
# ============================================================================

def get_admin_dashboard_stats() -> dict[str, int | float]:
    """Get statistics for admin dashboard."""
    return {
        "total_posts": Post.objects.count(),
        "published_posts": Post.objects.filter(status=Post.Status.PUBLISHED).count(),
        "draft_posts": Post.objects.filter(status=Post.Status.DRAFT).count(),
        "pending_comments": Comment.objects.filter(is_approved=False).count(),
        "avg_seo_score": (
            Post.objects.filter(status=Post.Status.PUBLISHED).aggregate(
                avg_score=Avg("seo_audit_score")
            )["avg_score"] or 0
        ),
    }


def get_recent_published_posts(limit: int = 10) -> QuerySet[Post]:
    """Get most recent published posts."""
    return (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .select_related("author")
        .order_by("-published_at")[:limit]
    )


def get_pending_comments(limit: int = 5) -> QuerySet[Comment]:
    """Get pending (unapproved) comments."""
    return (
        Comment.objects.filter(is_approved=False)
        .select_related("post", "author")
        .order_by("-created_at")[:limit]
    )


def get_user_dashboard_stats(user: User) -> dict[str, int]:
    """Get dashboard statistics for a specific user."""
    user_posts = Post.objects.filter(author=user)
    
    return {
        "total_posts": user_posts.count(),
        "published_posts": user_posts.filter(status=Post.Status.PUBLISHED).count(),
        "draft_posts": user_posts.filter(status=Post.Status.DRAFT).count(),
        "total_views": PostView.objects.filter(post__author=user).aggregate(
            total=Count('id')
        )["total"] or 0,
        "total_likes": PostLike.objects.filter(post__author=user).count(),
        "total_bookmarks": PostBookmark.objects.filter(post__author=user).count(),
        "total_comments": Comment.objects.filter(post__author=user, is_approved=True).count(),
    }
