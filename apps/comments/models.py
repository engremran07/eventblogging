"""
Comments, reactions, and subscriber management models.
Fully pluggable - can be removed without affecting core blog functionality.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.db import models

User = get_user_model()


class Comment(models.Model):
    """User comment on a post."""

    post = models.ForeignKey("blog.Post", on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_comments")
    body = models.TextField(validators=[MinLengthValidator(3)])
    is_approved = models.BooleanField(default=True)
    moderation_score = models.PositiveSmallIntegerField(default=0, editable=False)
    moderation_reasons = models.JSONField(default=list, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["post", "is_approved", "created_at"]),
            models.Index(fields=["author", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Comment by {self.author} on {self.post}"


class PostLike(models.Model):
    """User reaction: like/heart on a post."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="liked_posts")
    post = models.ForeignKey("blog.Post", on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_post_like")
        ]
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} likes {self.post}"


class PostBookmark(models.Model):
    """User saved/bookmarked a post for later."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookmarked_posts")
    post = models.ForeignKey("blog.Post", on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_post_bookmark",
            )
        ]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["post", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} bookmarked {self.post}"


class PostView(models.Model):
    """Tracks page views for analytics."""

    post = models.ForeignKey("blog.Post", on_delete=models.CASCADE, related_name="view_events")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="post_views",
    )
    session_key = models.CharField(max_length=80, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["session_key"]),
            models.Index(fields=["viewed_at"]),
            models.Index(fields=["post", "viewed_at"]),
            models.Index(fields=["user", "-viewed_at"]),
        ]

    def __str__(self) -> str:
        return f"View for {self.post}"


class PostRevision(models.Model):
    """Versioning/audit trail for post edits."""

    post = models.ForeignKey("blog.Post", on_delete=models.CASCADE, related_name="revisions")
    editor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="post_revisions",
    )
    title = models.CharField(max_length=220)
    subtitle = models.CharField(max_length=260, blank=True)
    excerpt = models.CharField(max_length=320, blank=True)
    body_markdown = models.TextField()
    body_html = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("published", "Published")])
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["editor", "created_at"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Revision {self.pk} for {self.post}"


class NewsletterSubscriber(models.Model):
    """Email newsletter subscribers."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=120, default="site")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["email", "is_active"])]

    def __str__(self) -> str:
        return self.email
