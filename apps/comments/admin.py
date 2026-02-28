"""Django admin interface for comments and reactions."""

from django.contrib import admin

from core.constants import ADMIN_PAGINATION_SIZE
from .models import Comment, NewsletterSubscriber, PostBookmark, PostLike, PostRevision, PostView


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    fields = ("author", "body", "is_approved", "created_at")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "author",
        "post",
        "approval_status",
        "moderation_score",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_approved", "created_at", "updated_at", "post", "author")
    search_fields = ("body", "author__username", "post__title")
    list_select_related = ("author", "post")
    ordering = ("-created_at",)
    list_per_page = ADMIN_PAGINATION_SIZE
    readonly_fields = ("moderation_score", "moderation_reasons", "created_at", "updated_at")
    actions = ("approve_selected", "unapprove_selected")
    fieldsets = (
        ("Post & Author", {"fields": ("post", "author")}),
        ("Content", {"fields": ("body",)}),
        ("Moderation", {"fields": ("is_approved", "moderation_score", "moderation_reasons")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Status")
    def approval_status(self, obj):
        return "Approved" if obj.is_approved else "Pending"

    @admin.action(description="Approve selected comments")
    def approve_selected(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f"{count} comments approved.")

    @admin.action(description="Unapprove selected comments")
    def unapprove_selected(self, request, queryset):
        count = queryset.update(is_approved=False)
        self.message_user(request, f"{count} comments moved to pending.")


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "post__title")
    readonly_fields = ("created_at",)
    list_per_page = ADMIN_PAGINATION_SIZE


@admin.register(PostBookmark)
class PostBookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "post__title")
    readonly_fields = ("created_at",)
    list_per_page = ADMIN_PAGINATION_SIZE


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "session_fingerprint", "viewed_at")
    list_filter = ("viewed_at",)
    search_fields = ("post__title", "user__username", "session_key")
    readonly_fields = ("viewed_at",)
    list_per_page = ADMIN_PAGINATION_SIZE

    @admin.display(description="Session Fingerprint")
    def session_fingerprint(self, obj):
        if not obj.session_key:
            return ""
        if len(obj.session_key) <= 20:
            return obj.session_key
        return f"{obj.session_key[:20]}..."


@admin.register(PostRevision)
class PostRevisionAdmin(admin.ModelAdmin):
    list_display = ("post", "editor", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("post__title", "title", "editor__username")
    readonly_fields = ("created_at",)
    list_per_page = ADMIN_PAGINATION_SIZE
    fieldsets = (
        ("Post", {"fields": ("post", "editor")}),
        ("Content", {"fields": ("title", "subtitle", "excerpt", "body_markdown", "body_html")}),
        ("Status & Notes", {"fields": ("status", "note")}),
        ("Created", {"fields": ("created_at",), "classes": ("collapse",)}),
    )


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "is_active", "source", "created_at")
    list_filter = ("is_active", "source", "created_at")
    search_fields = ("email", "full_name")
    readonly_fields = ("created_at", "updated_at")
    list_per_page = ADMIN_PAGINATION_SIZE
    fieldsets = (
        ("Contact", {"fields": ("email", "full_name")}),
        ("Status", {"fields": ("is_active", "source")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ["activate_subscribers", "deactivate_subscribers"]

    @admin.action(description="Activate selected subscribers")
    def activate_subscribers(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected subscribers")
    def deactivate_subscribers(self, request, queryset):
        queryset.update(is_active=False)
