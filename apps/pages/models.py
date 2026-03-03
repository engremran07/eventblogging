from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, ClassVar

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from blog.models import render_markdown_to_safe_html

User = get_user_model()


class PageQuerySet(models.QuerySet["Page"]):
    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        from .policies import POLICY_SLUGS

        if self.filter(slug__in=POLICY_SLUGS).exists():
            raise ValidationError("Policy pages are protected and cannot be deleted.")
        return super().delete(*args, **kwargs)

    def published(self) -> PageQuerySet:
        return self.filter(
            status=Page.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )

    def visible_to(self, user: Any) -> PageQuerySet:
        visible = models.Q(
            status=Page.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )
        if user and user.is_authenticated:
            return self.filter(visible | models.Q(author=user))
        return self.filter(visible)

    def search(self, query: str) -> PageQuerySet:
        text = (query or "").strip()
        if not text:
            return self
        return self.filter(
            models.Q(title__icontains=text)
            | models.Q(summary__icontains=text)
            | models.Q(body_markdown__icontains=text)
            | models.Q(slug__icontains=text)
        )


class Page(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "In Review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class TemplateKey(models.TextChoices):
        DEFAULT = "default", "Default"
        LANDING = "landing", "Landing"
        DOCUMENTATION = "documentation", "Documentation"

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pages",
    )
    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    nav_label = models.CharField(max_length=90, blank=True)
    summary = models.CharField(max_length=320, blank=True)

    body_markdown = models.TextField()
    body_html = models.TextField(blank=True, editable=False)

    template_key = models.CharField(
        max_length=20,
        choices=TemplateKey.choices,
        default=TemplateKey.DEFAULT,
    )
    show_in_navigation = models.BooleanField(default=False)
    nav_order = models.PositiveSmallIntegerField(default=100)
    is_featured = models.BooleanField(default=False)

    cover_media = models.ForeignKey(
        "media.MediaFile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cover_for_pages",
        help_text="Managed media file for the cover image.",
    )
    cover_media_id: int | None

    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=170, blank=True)
    canonical_url = models.URLField(blank=True)

    # SEO structured data & suggestions
    schema_markup: Any = models.JSONField(default=dict, blank=True, editable=False)  # type: ignore[assignment]
    suggested_internal_links: Any = models.JSONField(default=list, blank=True, editable=False)  # type: ignore[assignment]

    # SEO algorithmic signals (populated by seo.services.compute_content_signals)
    tfidf_vector: Any = models.JSONField(default=dict, blank=True, editable=False, help_text="TF-IDF scores per term")  # type: ignore[assignment]
    keyword_index: Any = models.JSONField(default=dict, blank=True, editable=False, help_text="Keyword → anchor variants mapping")  # type: ignore[assignment]
    search_intent = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ("informational", "Informational"),
            ("transactional", "Transactional"),
            ("navigational", "Navigational"),
            ("commercial", "Commercial"),
        ],
        editable=False,
    )
    thin_content_score = models.PositiveSmallIntegerField(default=0, editable=False, help_text="0-10 score")
    seo_audit_score = models.PositiveSmallIntegerField(default=0, editable=False, help_text="0-100 score")
    seo_audit_results: Any = models.JSONField(default=list, blank=True, editable=False, help_text="Audit check results")  # type: ignore[assignment]
    flesch_score = models.SmallIntegerField(default=0, editable=False, help_text="Flesch-Kincaid readability 0-100")
    keyword_density = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0"), editable=False, help_text="Primary keyword density %")
    heading_count = models.PositiveSmallIntegerField(default=0, editable=False)
    image_count = models.PositiveSmallIntegerField(default=0, editable=False)
    internal_link_count = models.PositiveSmallIntegerField(default=0, editable=False)
    inbound_link_count = models.PositiveSmallIntegerField(default=0, editable=False)
    is_orphan = models.BooleanField(default=True, editable=False, help_text="No inbound links")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    word_count = models.PositiveIntegerField(default=0, editable=False)
    reading_time = models.PositiveSmallIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: ClassVar[PageQuerySet] = PageQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        ordering = ("nav_order", "title")
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["show_in_navigation", "nav_order"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("pages:detail", kwargs={"slug": self.slug})

    @property
    def effective_nav_label(self) -> str:
        return self.nav_label or self.title

    def _build_unique_slug(self) -> str:
        base_slug = slugify(self.title)[:220] or "page"
        slug = base_slug
        suffix = 2
        while Page.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f"{base_slug[:210]}-{suffix}"
            suffix += 1
        return slug

    def _build_word_count(self) -> int:
        return max(len((self.body_markdown or "").split()), 1)

    def _build_reading_time(self) -> int:
        return max(math.ceil(self.word_count / 220), 1)

    def publish(self) -> None:
        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    def record_revision(self, editor: Any = None, note: str = "") -> PageRevision:
        return PageRevision.objects.create(
            page=self,
            editor=editor,
            title=self.title,
            summary=self.summary,
            body_markdown=self.body_markdown,
            body_html=self.body_html,
            status=self.status,
            note=note,
        )

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        from .policies import POLICY_SLUGS

        if self.slug in POLICY_SLUGS:
            raise ValidationError("Policy pages are protected and cannot be deleted.")
        return super().delete(*args, **kwargs)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = self._build_unique_slug()

        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()

        self.word_count = self._build_word_count()
        self.reading_time = self._build_reading_time()
        self.body_html = render_markdown_to_safe_html(self.body_markdown)

        # meta_title / meta_description auto-fill handled by seo signal pipeline
        # (seo.signals._apply_page_metadata → seo.metadata.apply_auto_metadata_to_instance)

        super().save(*args, **kwargs)


class PageRevision(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="revisions")
    editor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_revisions",
    )
    title = models.CharField(max_length=220)
    summary = models.CharField(max_length=320, blank=True)
    body_markdown = models.TextField()
    body_html = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Page.Status.choices)
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["page", "created_at"])]

    def __str__(self) -> str:
        return f"Revision {self.pk} for {self.page}"
