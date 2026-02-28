from __future__ import annotations

import math

import bleach
import markdown
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from tagulous.models import SingleTagField, TagField
try:
    from bleach.css_sanitizer import CSSSanitizer
except Exception:  # pragma: no cover - optional dependency guard
    CSSSanitizer = None

User = get_user_model()

ALLOWED_HTML_TAGS = bleach.sanitizer.ALLOWED_TAGS.union(
    {
        "div",
        "p",
        "pre",
        "code",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "ul",
        "ol",
        "li",
        "hr",
        "img",
        "span",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "tfoot",
        "colgroup",
        "col",
        "font",
    }
)

ALLOWED_CSS_PROPERTIES = [
    "color",
    "background-color",
    "font-size",
    "font-family",
    "font-style",
    "font-weight",
    "text-decoration",
    "text-align",
    "line-height",
    "letter-spacing",
    "vertical-align",
    "width",
    "height",
    "border",
    "border-color",
    "border-width",
    "border-style",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
]

CSS_SANITIZER = (
    CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
    if CSSSanitizer is not None
    else None
)

ALLOWED_HTML_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "loading"],
    "code": ["class"],
    "span": ["class", "style"],
    "font": ["color", "face", "size", "style"],
    "p": ["style"],
    "div": ["style"],
    "blockquote": ["style"],
    "table": ["class", "style"],
    "thead": ["style"],
    "tbody": ["style"],
    "tfoot": ["style"],
    "tr": ["style"],
    "th": ["colspan", "rowspan", "style"],
    "td": ["colspan", "rowspan", "style"],
    "colgroup": ["span", "style"],
    "col": ["span", "style"],
}

if CSS_SANITIZER is None:
    for element_name, attrs in list(ALLOWED_HTML_ATTRIBUTES.items()):
        if "style" in attrs:
            ALLOWED_HTML_ATTRIBUTES[element_name] = [attr for attr in attrs if attr != "style"]


def render_markdown_to_safe_html(markdown_text: str) -> str:
    rendered = markdown.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "nl2br", "tables", "toc"],
    )
    clean_kwargs = {
        "tags": ALLOWED_HTML_TAGS,
        "attributes": ALLOWED_HTML_ATTRIBUTES,
        "protocols": ["http", "https", "mailto"],
        "strip": True,
    }
    if CSS_SANITIZER is not None:
        clean_kwargs["css_sanitizer"] = CSS_SANITIZER
    return bleach.clean(
        rendered,
        **clean_kwargs,
    )


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(
            status=Post.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )

    def visible_to(self, user):
        public_posts = Q(
            status=Post.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )
        if user and user.is_authenticated:
            return self.filter(public_posts | Q(author=user))
        return self.filter(public_posts)

    def editor_picks(self):
        return self.published().filter(is_editors_pick=True)

    def search(self, text: str):
        clean_text = text.strip()
        if not clean_text:
            return self

        # Use PostgreSQL FTS if search_vector is available
        from django.contrib.postgres.search import SearchQuery, SearchRank

        try:
            search_query = SearchQuery(clean_text, config="english", search_type="websearch")
            return (
                self.annotate(
                    search_rank=SearchRank("search_vector", search_query)
                )
                .filter(search_vector=search_query)
                .order_by("-search_rank")
            )
        except Exception:
            # Fallback to ILIKE if FTS fails
            return self.filter(
                Q(title__icontains=clean_text)
                | Q(subtitle__icontains=clean_text)
                | Q(excerpt__icontains=clean_text)
                | Q(body_markdown__icontains=clean_text)
                | Q(tags__name__icontains=clean_text)
                | Q(categories__name__icontains=clean_text)
            )

    def with_reaction_counts(self):
        return self.annotate(
            like_total=Count("likes", distinct=True),
            bookmark_total=Count("bookmarks", distinct=True),
            comment_total=Count(
                "comments",
                filter=Q(comments__is_approved=True),
                distinct=True,
            ),
        )


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "In Review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    title = models.CharField(max_length=220)
    subtitle = models.CharField(max_length=260, blank=True)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    excerpt = models.CharField(max_length=320, blank=True)
    body_markdown = models.TextField()
    body_html = models.TextField(blank=True, editable=False)
    search_vector = SearchVectorField(null=True, blank=True, editable=False, help_text="PostgreSQL FTS vector")
    cover_image = models.ImageField(upload_to="post-covers/", blank=True)

    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=170, blank=True)
    canonical_url = models.URLField(blank=True)
    robots = models.CharField(
        max_length=100,
        blank=True,
        default="index, follow",
        help_text="Meta robots directive",
    )
    og_image = models.URLField(blank=True, help_text="Open Graph image URL")

    primary_topic = SingleTagField(
        blank=True,
        initial="technology,engineering,product,design",
        autocomplete_initial=True,
        autocomplete_view="blog:topic_autocomplete",
        force_lowercase=True,
    )
    tags = TagField(
        blank=True,
        initial="django,python,web,htmx,alpinejs,bootstrap",
        autocomplete_initial=True,
        autocomplete_view="blog:tag_autocomplete",
        autocomplete_view_fulltext=True,
        force_lowercase=True,
        max_count=25,
        space_delimiter=False,
    )
    categories = TagField(
        blank=True,
        tree=True,
        initial=(
            "technology/django,technology/frontend,technology/backend,"
            "writing/tutorial,writing/deep-dive"
        ),
        autocomplete_initial=True,
        autocomplete_view="blog:category_autocomplete",
        autocomplete_view_fulltext=True,
        force_lowercase=True,
        max_count=15,
        space_delimiter=False,
    )

    # Stores the last deterministic auto-tag pass for manual+auto merge workflows.
    auto_tags = models.JSONField(default=list, blank=True, editable=False)
    auto_categories = models.JSONField(default=list, blank=True, editable=False)
    auto_primary_topic = models.CharField(max_length=255, blank=True, editable=False)
    auto_tagging_updated_at = models.DateTimeField(null=True, blank=True, editable=False)

    schema_markup = models.JSONField(default=dict, blank=True, editable=False)
    suggested_internal_links = models.JSONField(default=list, blank=True, editable=False)

    # SEO algorithmic signals
    tfidf_vector = models.JSONField(default=dict, blank=True, editable=False, help_text="TF-IDF scores per term")
    auto_tags_raw = models.JSONField(default=list, blank=True, editable=False, help_text="Raw auto-generated tags from BM25")
    keyword_index = models.JSONField(default=dict, blank=True, editable=False, help_text="Keyword → anchor variants mapping")
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
    seo_audit_results = models.JSONField(default=list, blank=True, editable=False, help_text="25-point audit results")

    # Content signals
    flesch_score = models.SmallIntegerField(default=0, editable=False, help_text="Flesch-Kincaid readability 0-100")
    keyword_density = models.DecimalField(max_digits=4, decimal_places=2, default=0, editable=False, help_text="Primary keyword density %")
    heading_count = models.PositiveSmallIntegerField(default=0, editable=False)
    image_count = models.PositiveSmallIntegerField(default=0, editable=False)
    internal_link_count = models.PositiveSmallIntegerField(default=0, editable=False)
    inbound_link_count = models.PositiveSmallIntegerField(default=0, editable=False)
    is_orphan = models.BooleanField(default=True, editable=False, help_text="No inbound links")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    is_editors_pick = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    allow_reactions = models.BooleanField(default=True)

    word_count = models.PositiveIntegerField(default=0, editable=False)
    reading_time = models.PositiveSmallIntegerField(default=1)
    views_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ("-published_at", "-created_at")
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["is_editors_pick", "is_featured"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["author", "status", "published_at"]),
            models.Index(fields=["is_featured", "-published_at"]),
            models.Index(fields=["-updated_at"]),
            # Partial indexes for common queries (PostgreSQL optimization)
            models.Index(
                fields=["status", "-published_at"],
                condition=models.Q(status="published"),
                name="blog_post_published_idx",
            ),
            models.Index(
                fields=["-published_at"],
                condition=models.Q(status="published", is_featured=True),
                name="blog_post_featured_idx",
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    @property
    def effective_meta_title(self):
        return self.meta_title or self.title

    @property
    def effective_meta_description(self):
        if self.meta_description:
            return self.meta_description
        if self.excerpt:
            return self.excerpt
        return (self.body_markdown or "")[:160]

    def publish(self):
        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    def record_revision(self, editor=None, note=""):
        from comments.models import PostRevision

        return PostRevision.objects.create(
            post=self,
            editor=editor,
            title=self.title,
            subtitle=self.subtitle,
            excerpt=self.excerpt,
            body_markdown=self.body_markdown,
            body_html=self.body_html,
            status=self.status,
            note=note,
        )

    def _build_unique_slug(self):
        base_slug = slugify(self.title)[:220] or "post"
        slug = base_slug
        suffix = 2

        while Post.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f"{base_slug[:210]}-{suffix}"
            suffix += 1

        return slug

    def _build_word_count(self):
        return max(len(self.body_markdown.split()), 1)

    def _build_reading_time(self):
        return max(math.ceil(self.word_count / 220), 1)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_unique_slug()

        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()

        self.word_count = self._build_word_count()
        self.reading_time = self._build_reading_time()
        self.body_html = render_markdown_to_safe_html(self.body_markdown)

        if not self.meta_title:
            self.meta_title = self.title[:70]
        if not self.meta_description:
            seed = self.excerpt or self.body_markdown
            self.meta_description = seed[:170]

        super().save(*args, **kwargs)

        # SearchVector expressions cannot be used on INSERT values in Django 6.
        # Persist the row first, then update the tsvector with a queryset update.
        Post.objects.filter(pk=self.pk).update(
            search_vector=SearchVector("title", weight="A", config="english")
            + SearchVector("subtitle", weight="B", config="english")
            + SearchVector("excerpt", weight="B", config="english")
            + SearchVector("body_markdown", weight="C", config="english")
        )


class ContentRefreshSettings(models.Model):
    """Settings for automatic content refresh/republish."""

    singleton_key = models.CharField(max_length=40, unique=True, default="global")
    auto_refresh_enabled = models.BooleanField(default=False)
    post_refresh_interval_hours = models.PositiveIntegerField(default=168)
    page_refresh_interval_hours = models.PositiveIntegerField(default=168)
    max_items_per_run = models.PositiveIntegerField(default=200)
    last_run_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Content Refresh Timer"
        verbose_name_plural = "Content Refresh Timer"

    def __str__(self):
        return "Content Refresh Timer"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(singleton_key="global")
        return obj
