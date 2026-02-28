from __future__ import annotations

from django.contrib import admin, messages

from .models import (
    SeoAuditSnapshot,
    SeoEngineSettings,
    SeoIssue,
    SeoLinkEdge,
    SeoMetadataLock,
    SeoRedirectRule,
    SeoRouteProfile,
    SeoScanJob,
    SeoScanJobItem,
    SeoSuggestion,
    SeoSuggestionRevision,
    TaxonomySynonymGroup,
    TaxonomySynonymTerm,
)
from .services import approve_suggestion, reject_suggestion


class SingletonAdminMixin(admin.ModelAdmin):
    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeoEngineSettings)
class SeoEngineSettingsAdmin(SingletonAdminMixin):
    list_display = (
        "enable_checks",
        "auto_fix_enabled",
        "min_links_per_doc",
        "whitehat_cap_max_links",
        "link_suggestion_min_score",
        "autopilot_min_confidence",
        "updated_at",
    )
    readonly_fields = ("singleton_key", "updated_at")
    fieldsets = (
        (
            "Engine",
            {
                "fields": (
                    "singleton_key",
                    "enable_checks",
                    "enable_live_checks",
                    "warn_only",
                    "admin_visibility_only",
                    "updated_at",
                )
            },
        ),
        (
            "Autofix",
            {
                "fields": (
                    "auto_fix_enabled",
                    "auto_fix_after_hours",
                    "apply_interlinks_on_audit",
                    "auto_update_published_links",
                )
            },
        ),
        (
            "Interlink Policy (White-Hat)",
            {
                "fields": (
                    "min_links_per_doc",
                    "whitehat_cap_max_links",
                    "rotation_interval_hours",
                    "rotation_churn_limit_percent",
                    "link_suggestion_min_score",
                    "autopilot_min_confidence",
                )
            },
        ),
        (
            "Crawl and Canonical Controls",
            {
                "fields": (
                    "stale_days_threshold",
                    "noindex_paginated_filters",
                    "canonical_query_allowlist",
                )
            },
        ),
    )


@admin.register(SeoRouteProfile)
class SeoRouteProfileAdmin(admin.ModelAdmin):
    list_display = (
        "route_name",
        "robots_default",
        "og_type",
        "priority",
        "changefreq",
        "enabled",
        "updated_at",
    )
    list_filter = ("enabled", "changefreq", "og_type")
    search_fields = ("route_name", "title_template", "description_template")


class SeoIssueInline(admin.TabularInline):
    model = SeoIssue
    extra = 0
    can_delete = False
    fields = ("check_key", "severity", "status", "message", "autofixable")
    readonly_fields = fields


@admin.register(SeoAuditSnapshot)
class SeoAuditSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "route_type",
        "url",
        "score",
        "critical_count",
        "warning_count",
        "failed_count",
        "trigger",
        "audited_at",
    )
    list_filter = ("route_type", "trigger", "audited_at")
    search_fields = ("url", "checksum")
    inlines = [SeoIssueInline]
    readonly_fields = (
        "content_type",
        "object_id",
        "url",
        "route_type",
        "score",
        "critical_count",
        "warning_count",
        "passed_count",
        "failed_count",
        "trigger",
        "metadata_json",
        "checksum",
        "audited_at",
        "auto_fixed_at",
    )


@admin.register(SeoIssue)
class SeoIssueAdmin(admin.ModelAdmin):
    list_display = ("id", "check_key", "severity", "status", "snapshot", "created_at")
    list_filter = ("severity", "status", "check_key")
    search_fields = ("check_key", "message", "suggested_fix")
    readonly_fields = ("snapshot", "check_key", "severity", "message", "details_json", "created_at")


@admin.register(SeoSuggestion)
class SeoSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "suggestion_type",
        "status",
        "content_type",
        "object_id",
        "confidence",
        "created_at",
        "applied_at",
    )
    list_filter = ("suggestion_type", "status", "created_at")
    search_fields = ("content_type__model", "payload_json")
    readonly_fields = ("content_type", "object_id", "suggestion_type", "payload_json", "created_at")
    actions = ("approve_selected", "reject_selected")

    @admin.action(description="Approve selected suggestions")
    def approve_selected(self, request, queryset):
        approved = 0
        skipped = 0
        for suggestion in queryset:
            result = approve_suggestion(suggestion.id, reviewer=request.user)
            if result.get("ok"):
                approved += 1
            else:
                skipped += 1
        if approved:
            self.message_user(request, f"{approved} suggestions approved.", messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"{skipped} suggestions skipped (already processed or invalid).",
                messages.WARNING,
            )

    @admin.action(description="Reject selected suggestions")
    def reject_selected(self, request, queryset):
        rejected = 0
        skipped = 0
        for suggestion in queryset:
            result = reject_suggestion(suggestion.id)
            if result.get("ok"):
                rejected += 1
            else:
                skipped += 1
        if rejected:
            self.message_user(request, f"{rejected} suggestions rejected.", messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"{skipped} suggestions skipped (already processed or invalid).",
                messages.WARNING,
            )


@admin.register(SeoRedirectRule)
class SeoRedirectRuleAdmin(admin.ModelAdmin):
    list_display = (
        "old_path",
        "target_url",
        "status_code",
        "is_active",
        "hits",
        "last_hit_at",
        "updated_at",
    )
    list_filter = ("status_code", "is_active")
    search_fields = ("old_path", "target_url", "source_model", "notes")


@admin.register(SeoLinkEdge)
class SeoLinkEdgeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_content_type",
        "source_object_id",
        "target_content_type",
        "target_object_id",
        "anchor_text",
        "status",
        "confidence",
        "created_at",
    )
    list_filter = ("status", "source_content_type", "target_content_type")
    search_fields = ("anchor_text",)


@admin.register(SeoMetadataLock)
class SeoMetadataLockAdmin(admin.ModelAdmin):
    list_display = (
        "content_type",
        "object_id",
        "lock_title",
        "lock_description",
        "lock_canonical",
        "lock_og",
        "lock_twitter",
        "updated_at",
    )
    list_filter = ("content_type", "lock_title", "lock_description", "lock_canonical")


@admin.register(SeoScanJob)
class SeoScanJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_type",
        "status",
        "trigger",
        "processed_items",
        "total_items",
        "error_count",
        "warning_count",
        "started_at",
        "finished_at",
    )
    list_filter = ("job_type", "status", "trigger", "created_at")
    readonly_fields = (
        "job_type",
        "status",
        "trigger",
        "started_by",
        "started_at",
        "finished_at",
        "total_items",
        "processed_items",
        "error_count",
        "warning_count",
        "snapshot_count",
        "canceled_requested",
        "settings_snapshot_json",
        "notes",
        "last_error",
        "created_at",
        "updated_at",
    )


@admin.register(SeoScanJobItem)
class SeoScanJobItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job",
        "content_type",
        "object_id",
        "status",
        "score",
        "critical_count",
        "warning_count",
        "duration_ms",
    )
    list_filter = ("status", "content_type", "job__job_type")
    search_fields = ("url", "error_text")
    readonly_fields = (
        "job",
        "content_type",
        "object_id",
        "url",
        "status",
        "score",
        "critical_count",
        "warning_count",
        "duration_ms",
        "error_text",
        "started_at",
        "finished_at",
        "created_at",
    )


class TaxonomySynonymTermInline(admin.TabularInline):
    model = TaxonomySynonymTerm
    extra = 0
    fields = ("term", "normalized_term", "is_canonical", "weight", "is_active")
    readonly_fields = ("normalized_term",)


@admin.register(TaxonomySynonymGroup)
class TaxonomySynonymGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "is_active", "updated_at")
    list_filter = ("scope", "is_active")
    search_fields = ("name",)
    inlines = [TaxonomySynonymTermInline]


@admin.register(TaxonomySynonymTerm)
class TaxonomySynonymTermAdmin(admin.ModelAdmin):
    list_display = ("term", "group", "normalized_term", "is_canonical", "weight", "is_active")
    list_filter = ("group__scope", "is_canonical", "is_active")
    search_fields = ("term", "normalized_term", "group__name")


@admin.register(SeoSuggestionRevision)
class SeoSuggestionRevisionAdmin(admin.ModelAdmin):
    list_display = ("id", "suggestion", "edited_by", "edited_at")
    list_filter = ("edited_at",)
    search_fields = ("suggestion__id", "note")
    readonly_fields = (
        "suggestion",
        "edited_by",
        "edited_at",
        "old_payload_json",
        "new_payload_json",
        "note",
    )
