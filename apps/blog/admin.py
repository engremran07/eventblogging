from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from tagulous import admin as tag_admin

from core.utils import ADMIN_PAGINATION_SIZE
from seo.services import audit_content_batch

from .content_refresh import run_content_date_refresh
from .forms import PostForm
from .models import (
    ContentRefreshSettings,
    Post,
)
from .services import apply_auto_taxonomy_to_post
from .taxonomy_rules import validate_category_depth


class PostAdmin(admin.ModelAdmin):
    form = PostForm
    list_display = (
        "title",
        "author",
        "status",
        "is_featured",
        "is_editors_pick",
        "allow_reactions",
        "published_at",
        "created_at",
        "updated_at",
        "views_count",
    )
    list_filter = (
        "status",
        "is_featured",
        "is_editors_pick",
        "allow_comments",
        "allow_reactions",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "title",
        "subtitle",
        "excerpt",
        "body_markdown",
        "meta_title",
        "meta_description",
    )
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = (
        "word_count",
        "reading_time",
        "views_count",
        "auto_tagging_updated_at",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "published_at"
    list_per_page = ADMIN_PAGINATION_SIZE
    inlines = []
    actions = (
        "publish_selected",
        "move_to_review",
        "archive_selected",
        "feature_selected",
        "unfeature_selected",
        "enable_comments",
        "disable_comments",
        "enable_reactions",
        "disable_reactions",
        "refresh_updated_date_now",
    )

    def _refresh_auto_taxonomy(self, queryset):
        for post in queryset.prefetch_related("tags", "categories"):
            apply_auto_taxonomy_to_post(post)

    def _refresh_seo(self, queryset):
        audit_content_batch(
            "post",
            queryset.values_list("id", flat=True),
            trigger="save",
            run_autopilot=True,
        )

    @admin.action(description="Publish selected posts")
    def publish_selected(self, request, queryset):
        count = queryset.update(
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self._refresh_auto_taxonomy(queryset)
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} posts published.", messages.SUCCESS)

    @admin.action(description="Move selected posts to review")
    def move_to_review(self, request, queryset):
        count = queryset.update(status=Post.Status.REVIEW, updated_at=timezone.now())
        self._refresh_auto_taxonomy(queryset)
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} posts moved to review.", messages.SUCCESS)

    @admin.action(description="Archive selected posts")
    def archive_selected(self, request, queryset):
        count = queryset.update(status=Post.Status.ARCHIVED, updated_at=timezone.now())
        self._refresh_auto_taxonomy(queryset)
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} posts archived.", messages.SUCCESS)

    @admin.action(description="Mark selected posts as featured")
    def feature_selected(self, request, queryset):
        count = queryset.update(is_featured=True, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} posts marked as featured.", messages.SUCCESS)

    @admin.action(description="Remove selected posts from featured")
    def unfeature_selected(self, request, queryset):
        count = queryset.update(is_featured=False, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} posts unfeatured.", messages.SUCCESS)

    @admin.action(description="Enable comments on selected posts")
    def enable_comments(self, request, queryset):
        count = queryset.update(allow_comments=True, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"Comments enabled for {count} posts.", messages.SUCCESS)

    @admin.action(description="Disable comments on selected posts")
    def disable_comments(self, request, queryset):
        count = queryset.update(allow_comments=False, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"Comments disabled for {count} posts.", messages.SUCCESS)

    @admin.action(description="Enable reactions on selected posts")
    def enable_reactions(self, request, queryset):
        count = queryset.update(allow_reactions=True, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"Reactions enabled for {count} posts.", messages.SUCCESS)

    @admin.action(description="Disable reactions on selected posts")
    def disable_reactions(self, request, queryset):
        count = queryset.update(allow_reactions=False, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"Reactions disabled for {count} posts.", messages.SUCCESS)

    @admin.action(description="Refresh updated date now for selected posts")
    def refresh_updated_date_now(self, request, queryset):
        count = queryset.update(updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} posts updated with new timestamp.", messages.SUCCESS)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance and form.instance.pk:
            apply_auto_taxonomy_to_post(form.instance)


@admin.register(ContentRefreshSettings)
class ContentRefreshSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "singleton_key",
        "auto_refresh_enabled",
        "post_refresh_interval_hours",
        "page_refresh_interval_hours",
        "max_items_per_run",
        "last_run_at",
        "updated_at",
    )
    readonly_fields = ("singleton_key", "last_run_at", "updated_at")
    actions = ("trigger_refresh_now",)

    def has_add_permission(self, request):
        if ContentRefreshSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    @admin.action(description="Trigger refresh now (ignore interval once)")
    def trigger_refresh_now(self, request, queryset):
        result = run_content_date_refresh(force=True)
        self.message_user(
            request,
            (
                f"Refresh complete: {result['posts_updated']} posts and "
                f"{result['pages_updated']} pages timestamped now."
            ),
            messages.SUCCESS,
        )


class TagBulkActionsMixin:
    actions = ("merge_tags", "mark_protected", "mark_unprotected", "refresh_usage_counts")

    @admin.action(description="Protect selected tags")
    def mark_protected(self, request, queryset):
        count = queryset.update(protected=True)
        self.message_user(request, f"{count} tags protected.", messages.SUCCESS)

    @admin.action(description="Unprotect selected tags")
    def mark_unprotected(self, request, queryset):
        count = queryset.update(protected=False)
        self.message_user(request, f"{count} tags unprotected.", messages.SUCCESS)

    @admin.action(description="Recalculate usage counts for selected tags")
    def refresh_usage_counts(self, request, queryset):
        updated = 0
        for tag in queryset:
            tag.update_count()
            updated += 1
        self.message_user(request, f"Usage counts refreshed for {updated} tags.", messages.SUCCESS)


class FlatTagAdmin(TagBulkActionsMixin, tag_admin.TagModelAdmin):
    list_display = ("name", "count", "protected")
    list_display_links = ("name",)
    list_filter = ("protected",)
    search_fields = ("name", "slug")
    prepopulated_fields = {}
    ordering = ("-count", "name")
    readonly_fields = ("slug", "count")
    list_per_page = ADMIN_PAGINATION_SIZE

    def get_prepopulated_fields(self, request, obj=None):
        # Some Tagulous generated forms expose only name/protected; never require slug in add form.
        return {}


class TopicTagAdmin(FlatTagAdmin):
    pass


class GenericTagAdmin(FlatTagAdmin):
    pass


class CategoryTagAdminForm(forms.ModelForm):
    class Meta:
        model = Post.categories.tag_model
        fields = ["name", "parent", "protected"]

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        validate_category_depth([name])
        return name


class CategoryTagAdmin(TagBulkActionsMixin, tag_admin.TagTreeModelAdmin):
    form = CategoryTagAdminForm
    list_display = ("name", "parent", "level", "count", "protected")
    list_display_links = ("name",)
    list_filter = ("protected", "level")
    search_fields = ("name", "slug", "path", "label")
    prepopulated_fields = {}
    ordering = ("path",)
    readonly_fields = ("slug", "path", "level", "count", "label")
    list_per_page = ADMIN_PAGINATION_SIZE

    def get_prepopulated_fields(self, request, obj=None):
        # Some Tagulous generated forms expose only name/protected; never require slug in add form.
        return {}


# Register tagged model and generated tag models with Tagulous admin helpers.
tag_admin.register(Post, PostAdmin)
tag_admin.register(Post.primary_topic, TopicTagAdmin)
tag_admin.register(Post.tags, GenericTagAdmin)
tag_admin.register(Post.categories, CategoryTagAdmin)

# Ensure custom auth user admin with double-verification deletion is registered.
# Registration now lives in core/admin.py and is auto-discovered by Django.
