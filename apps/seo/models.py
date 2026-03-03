from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


User = get_user_model()


class SingletonSettingsModel(models.Model):
    singleton_key = models.CharField(max_length=40, unique=True, default="global")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(singleton_key="global")
        return obj


class SeoEngineSettings(SingletonSettingsModel):
    enable_checks = models.BooleanField(default=True)
    enable_live_checks = models.BooleanField(default=True)
    warn_only = models.BooleanField(default=True)
    admin_visibility_only = models.BooleanField(default=True)
    auto_fix_enabled = models.BooleanField(default=True)
    auto_fix_after_hours = models.PositiveIntegerField(default=168)
    rotation_interval_hours = models.PositiveIntegerField(default=24)
    min_links_per_doc = models.PositiveSmallIntegerField(default=3)
    whitehat_cap_max_links = models.PositiveSmallIntegerField(default=8)
    rotation_churn_limit_percent = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(100)],
    )
    stale_days_threshold = models.PositiveSmallIntegerField(default=30)
    noindex_paginated_filters = models.BooleanField(default=True)
    canonical_query_allowlist = models.CharField(max_length=255, blank=True)
    link_suggestion_min_score = models.FloatField(default=0.45)
    autopilot_min_confidence = models.FloatField(default=0.82)
    auto_update_published_links = models.BooleanField(default=True)
    apply_interlinks_on_audit = models.BooleanField(default=True)

    class Meta:
        verbose_name = "SEO Engine Settings"
        verbose_name_plural = "SEO Engine Settings"

    def __str__(self):
        return "SEO Engine Settings"


class SeoRouteProfile(models.Model):
    route_name = models.CharField(max_length=120, unique=True)
    title_template = models.CharField(max_length=180, blank=True)
    description_template = models.CharField(max_length=220, blank=True)
    robots_default = models.CharField(max_length=60, default="index,follow")
    og_type = models.CharField(max_length=30, default="website")
    priority = models.FloatField(default=0.6)
    changefreq = models.CharField(max_length=20, default="weekly")
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("route_name",)
        verbose_name = "SEO Route Profile"
        verbose_name_plural = "SEO Route Profiles"

    def __str__(self):
        return self.route_name


class SeoAuditSnapshot(models.Model):
    class RouteType(models.TextChoices):
        POST = "post", "Post"
        PAGE = "page", "Page"
        POLICY = "policy", "Policy"
        LISTING = "listing", "Listing"
        STATIC = "static", "Static"
        OTHER = "other", "Other"

    class Trigger(models.TextChoices):
        SAVE = "save", "Save"
        MANUAL = "manual", "Manual"
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        DELETE = "delete", "Delete"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    url = models.CharField(max_length=360)
    route_type = models.CharField(max_length=20, choices=RouteType.choices, default=RouteType.OTHER)
    score = models.FloatField(default=0.0)
    critical_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    passed_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    trigger = models.CharField(max_length=20, choices=Trigger.choices, default=Trigger.SAVE)
    metadata_json = models.JSONField(default=dict, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    audited_at = models.DateTimeField(auto_now_add=True)
    auto_fixed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-audited_at",)
        indexes = [
            models.Index(fields=["content_type", "object_id", "audited_at"]),
            models.Index(fields=["route_type", "audited_at"]),
            models.Index(fields=["score"]),
        ]
        verbose_name = "SEO Audit Snapshot"
        verbose_name_plural = "SEO Audit Snapshots"

    def __str__(self):
        return f"{self.route_type} audit {self.content_type_id}:{self.object_id} ({self.score:.1f})"


class SeoIssue(models.Model):
    class Severity(models.TextChoices):
        CRITICAL = "critical", "Critical"
        WARNING = "warning", "Warning"
        INFO = "info", "Info"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        AUTO_FIXED = "auto_fixed", "Auto-Fixed"
        FIXED = "fixed", "Fixed"
        IGNORED = "ignored", "Ignored"

    snapshot = models.ForeignKey(SeoAuditSnapshot, on_delete=models.CASCADE, related_name="issues")
    check_key = models.CharField(max_length=80)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    message = models.CharField(max_length=260)
    suggested_fix = models.CharField(max_length=260, blank=True)
    autofixable = models.BooleanField(default=False)
    details_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("severity", "-created_at")
        indexes = [
            models.Index(fields=["status", "severity"]),
            models.Index(fields=["check_key", "status"]),
        ]
        verbose_name = "SEO Issue"
        verbose_name_plural = "SEO Issues"

    def __str__(self):
        return f"{self.check_key} [{self.severity}]"


class SeoSuggestion(models.Model):
    id: int  # auto-generated BigAutoField PK

    class SuggestionType(models.TextChoices):
        METADATA = "metadata", "Metadata"
        INTERLINK = "interlink", "Interlink"
        REDIRECT = "redirect", "Redirect"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        NEEDS_CORRECTION = "needs_correction", "Needs Correction"
        APPLIED = "applied", "Applied"
        REJECTED = "rejected", "Rejected"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    suggestion_type = models.CharField(max_length=20, choices=SuggestionType.choices)
    payload_json = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["content_type", "object_id", "status"]),
            models.Index(fields=["suggestion_type", "status"]),
        ]
        verbose_name = "SEO Suggestion"
        verbose_name_plural = "SEO Suggestions"

    def __str__(self):
        return f"{self.suggestion_type} suggestion ({self.status})"


class SeoRedirectRule(models.Model):
    class StatusCode(models.IntegerChoices):
        MOVED_PERMANENTLY = 301, "301 Moved Permanently"
        FOUND = 302, "302 Found"
        GONE = 410, "410 Gone"

    old_path = models.CharField(max_length=320, unique=True)
    target_url = models.CharField(max_length=360, blank=True)
    status_code = models.PositiveSmallIntegerField(
        choices=StatusCode.choices,
        default=StatusCode.MOVED_PERMANENTLY,
    )
    is_active = models.BooleanField(default=True)
    source_model = models.CharField(max_length=120, blank=True)
    source_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    hits = models.PositiveIntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_redirect_rules",
    )
    notes = models.CharField(max_length=260, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("old_path",)
        indexes = [models.Index(fields=["is_active", "status_code"])]
        verbose_name = "SEO Redirect Rule"
        verbose_name_plural = "SEO Redirect Rules"

    def __str__(self):
        return f"{self.old_path} -> {self.target_url or self.status_code}"


class SeoLinkEdge(models.Model):
    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        APPLIED = "applied", "Applied"
        REMOVED = "removed", "Removed"

    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="seo_outgoing_edges",
    )
    source_object_id = models.PositiveBigIntegerField()
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="seo_incoming_edges",
    )
    target_object_id = models.PositiveBigIntegerField()
    anchor_text = models.CharField(max_length=180)
    source_fragment_hash = models.CharField(max_length=40)
    confidence = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUGGESTED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["source_content_type", "source_object_id", "status"]),
            models.Index(fields=["target_content_type", "target_object_id", "status"]),
        ]
        verbose_name = "SEO Link Edge"
        verbose_name_plural = "SEO Link Edges"

    def __str__(self):
        return f"{self.anchor_text} ({self.status})"


class SeoMetadataLock(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    lock_title = models.BooleanField(default=False)
    lock_description = models.BooleanField(default=False)
    lock_canonical = models.BooleanField(default=False)
    lock_og = models.BooleanField(default=False)
    lock_twitter = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="unique_seo_metadata_lock_target",
            )
        ]
        verbose_name = "SEO Metadata Lock"
        verbose_name_plural = "SEO Metadata Locks"

    def __str__(self):
        return f"Locks for {self.content_type_id}:{self.object_id}"


class SeoScanJob(models.Model):
    id: int  # auto-generated BigAutoField PK
    items: RelatedManager[SeoScanJobItem]  # reverse FK from SeoScanJobItem.job

    class JobType(models.TextChoices):
        FULL = "full", "Full"
        POSTS = "posts", "Posts"
        PAGES = "pages", "Pages"
        CHANGED_ONLY = "changed_only", "Changed Only"
        INTERLINKS = "interlinks", "Internal Linking"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        SCHEDULED = "scheduled", "Scheduled"

    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.FULL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    trigger = models.CharField(max_length=20, choices=Trigger.choices, default=Trigger.MANUAL)
    started_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_scan_jobs",
    )
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    total_items = models.PositiveIntegerField(default=0)
    processed_items = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    snapshot_count = models.PositiveIntegerField(default=0)
    canceled_requested = models.BooleanField(default=False)
    settings_snapshot_json = models.JSONField(default=dict, blank=True)
    notes = models.CharField(max_length=280, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["job_type", "created_at"]),
        ]
        verbose_name = "SEO Scan Job"
        verbose_name_plural = "SEO Scan Jobs"

    def __str__(self):
        return f"{self.get_job_type_display()} scan ({self.status})"

    @property
    def progress_percent(self):
        if self.total_items <= 0:
            return 0
        return int((self.processed_items / self.total_items) * 100)


class SeoScanJobItem(models.Model):
    id: int  # auto-generated BigAutoField PK

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    job = models.ForeignKey(SeoScanJob, on_delete=models.CASCADE, related_name="items")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    url = models.CharField(max_length=360)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    score = models.FloatField(default=0.0)
    critical_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    error_text = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["job", "content_type", "object_id"],
                name="unique_scan_job_target",
            )
        ]
        indexes = [
            models.Index(fields=["job", "status"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        verbose_name = "SEO Scan Job Item"
        verbose_name_plural = "SEO Scan Job Items"

    def __str__(self):
        return f"Job {self.job_id} item {self.content_type_id}:{self.object_id}"


class TaxonomySynonymGroup(models.Model):
    id: int  # auto-generated BigAutoField PK

    class Scope(models.TextChoices):
        TAGS = "tags", "Tags"
        TOPICS = "topics", "Topics"
        CATEGORIES = "categories", "Categories"
        ALL = "all", "All"

    name = models.CharField(max_length=120)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.ALL)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["name", "scope"], name="unique_synonym_group_scope")
        ]
        indexes = [models.Index(fields=["scope", "is_active"])]
        verbose_name = "Taxonomy Synonym Group"
        verbose_name_plural = "Taxonomy Synonym Groups"

    def __str__(self):
        return f"{self.name} ({self.scope})"


class TaxonomySynonymTerm(models.Model):
    id: int  # auto-generated BigAutoField PK

    group = models.ForeignKey(
        TaxonomySynonymGroup,
        on_delete=models.CASCADE,
        related_name="terms",
    )
    term = models.CharField(max_length=160)
    normalized_term = models.CharField(max_length=160, editable=False)
    is_canonical = models.BooleanField(default=False)
    weight = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("group", "-is_canonical", "term")
        constraints = [
            models.UniqueConstraint(
                fields=["group", "normalized_term"],
                name="unique_synonym_term_per_group",
            )
        ]
        indexes = [
            models.Index(fields=["group", "is_active"]),
            models.Index(fields=["normalized_term"]),
        ]
        verbose_name = "Taxonomy Synonym Term"
        verbose_name_plural = "Taxonomy Synonym Terms"

    def __str__(self):
        return self.term

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.normalized_term = " ".join((self.term or "").lower().split()).strip()
        super().save(*args, **kwargs)


class SeoSuggestionRevision(models.Model):
    suggestion = models.ForeignKey(
        SeoSuggestion,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    edited_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_suggestion_revisions",
    )
    edited_at = models.DateTimeField(auto_now_add=True)
    old_payload_json = models.JSONField(default=dict, blank=True)
    new_payload_json = models.JSONField(default=dict, blank=True)
    note = models.CharField(max_length=280, blank=True)

    class Meta:
        ordering = ("-edited_at",)
        indexes = [models.Index(fields=["suggestion", "edited_at"])]
        verbose_name = "SEO Suggestion Revision"
        verbose_name_plural = "SEO Suggestion Revisions"

    def __str__(self):
        return f"Revision for suggestion {self.suggestion_id}"


class SeoChangeLog(models.Model):
    """Tracks every autonomous SEO change for admin visibility."""

    class ChangeType(models.TextChoices):
        INTERLINK_APPLIED = "interlink_applied", "Interlink Applied"
        META_TITLE_FIXED = "meta_title_fixed", "Meta Title Fixed"
        META_DESC_FIXED = "meta_desc_fixed", "Meta Description Fixed"
        CANONICAL_SET = "canonical_set", "Canonical Set"
        CANONICAL_FIXED = "canonical_fixed", "Canonical Fixed"
        METADATA_APPROVED = "metadata_approved", "Metadata Approved"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    change_type = models.CharField(max_length=30, choices=ChangeType.choices)
    field_name = models.CharField(max_length=60)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["content_type", "object_id", "created_at"]),
            models.Index(fields=["change_type", "created_at"]),
        ]
        verbose_name = "SEO Change Log"
        verbose_name_plural = "SEO Change Logs"

    def __str__(self) -> str:
        return f"{self.change_type} on {self.content_type_id}:{self.object_id}"
