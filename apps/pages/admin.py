from django.contrib import admin, messages
from django.utils import timezone
from core.constants import ADMIN_PAGINATION_SIZE

from .forms import PageForm
from .models import Page, PageRevision
from .policies import POLICY_SLUGS
from seo.services import audit_content_batch


class PageRevisionInline(admin.TabularInline):
    model = PageRevision
    extra = 0
    can_delete = False
    fields = ("editor", "status", "note", "created_at")
    readonly_fields = ("editor", "status", "note", "created_at")


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form = PageForm
    list_display = (
        "title",
        "author",
        "status",
        "template_key",
        "show_in_navigation",
        "nav_order",
        "is_featured",
        "published_at",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "author",
        "status",
        "template_key",
        "show_in_navigation",
        "is_featured",
        "published_at",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "title",
        "slug",
        "summary",
        "body_markdown",
        "meta_title",
        "nav_label",
        "author__username",
    )
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("word_count", "reading_time", "created_at", "updated_at")
    date_hierarchy = "published_at"
    inlines = [PageRevisionInline]
    list_per_page = ADMIN_PAGINATION_SIZE
    actions = (
        "publish_selected",
        "move_to_review",
        "archive_selected",
        "show_in_navigation_selected",
        "hide_from_navigation_selected",
        "feature_selected",
        "unfeature_selected",
        "set_template_default",
        "set_template_landing",
        "set_template_docs",
        "refresh_updated_date_now",
    )

    def _refresh_seo(self, queryset):
        audit_content_batch(
            "page",
            queryset.values_list("id", flat=True),
            trigger="save",
            run_autopilot=True,
        )

    @admin.action(description="Publish selected pages")
    def publish_selected(self, request, queryset):
        count = queryset.update(
            status=Page.Status.PUBLISHED,
            published_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages published.", messages.SUCCESS)

    @admin.action(description="Move selected pages to review")
    def move_to_review(self, request, queryset):
        count = queryset.update(status=Page.Status.REVIEW, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages moved to review.", messages.SUCCESS)

    @admin.action(description="Archive selected pages")
    def archive_selected(self, request, queryset):
        count = queryset.update(status=Page.Status.ARCHIVED, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages archived.", messages.SUCCESS)

    @admin.action(description="Show selected pages in navigation")
    def show_in_navigation_selected(self, request, queryset):
        count = queryset.update(show_in_navigation=True, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages shown in navigation.", messages.SUCCESS)

    @admin.action(description="Hide selected pages from navigation")
    def hide_from_navigation_selected(self, request, queryset):
        count = queryset.update(show_in_navigation=False, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages hidden from navigation.", messages.SUCCESS)

    @admin.action(description="Mark selected pages as featured")
    def feature_selected(self, request, queryset):
        count = queryset.update(is_featured=True, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages marked as featured.", messages.SUCCESS)

    @admin.action(description="Remove selected pages from featured")
    def unfeature_selected(self, request, queryset):
        count = queryset.update(is_featured=False, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages unfeatured.", messages.SUCCESS)

    @admin.action(description="Set selected pages to Default template")
    def set_template_default(self, request, queryset):
        count = queryset.update(template_key=Page.TemplateKey.DEFAULT, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages set to Default template.", messages.SUCCESS)

    @admin.action(description="Set selected pages to Landing template")
    def set_template_landing(self, request, queryset):
        count = queryset.update(template_key=Page.TemplateKey.LANDING, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages set to Landing template.", messages.SUCCESS)

    @admin.action(description="Set selected pages to Documentation template")
    def set_template_docs(self, request, queryset):
        count = queryset.update(template_key=Page.TemplateKey.DOCUMENTATION, updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages set to Documentation template.", messages.SUCCESS)

    @admin.action(description="Refresh updated date now for selected pages")
    def refresh_updated_date_now(self, request, queryset):
        count = queryset.update(updated_at=timezone.now())
        self._refresh_seo(queryset)
        self.message_user(request, f"{count} pages updated with new timestamp.", messages.SUCCESS)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.slug in POLICY_SLUGS:
            return False
        return super().has_delete_permission(request, obj=obj)

    def delete_model(self, request, obj):
        if obj.slug in POLICY_SLUGS:
            self.message_user(
                request,
                "Policy pages are protected and cannot be deleted.",
                messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        protected = queryset.filter(slug__in=POLICY_SLUGS)
        if protected.exists():
            self.message_user(
                request,
                "Policy pages are protected and were skipped during deletion.",
                messages.WARNING,
            )
        deletable = queryset.exclude(slug__in=POLICY_SLUGS)
        super().delete_queryset(request, deletable)


@admin.register(PageRevision)
class PageRevisionAdmin(admin.ModelAdmin):
    list_display = ("page", "editor", "status", "note", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("page__title", "editor__username", "note")
    readonly_fields = (
        "page",
        "editor",
        "title",
        "summary",
        "body_markdown",
        "body_html",
        "status",
        "note",
        "created_at",
    )
    list_per_page = ADMIN_PAGINATION_SIZE
