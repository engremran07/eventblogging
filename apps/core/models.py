"""
Core models for TAGULOUS blog platform.
All singleton settings models consolidated here.
"""

from __future__ import annotations
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from solo.models import SingletonModel

# ============================================================================
# BASE MODELS — Foundation for all app models
# ============================================================================

class BaseModel(models.Model):
    """
    Abstract base model for all project models.
    Provides consistent UUIDs, timestamps, and soft-delete support.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class SoftDeleteManager(models.Manager):
    """Manager that only returns active instances by default."""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SoftDeleteModel(BaseModel):
    """
    Base model with soft-delete support.
    Instances are marked inactive instead of deleted, preserving audit trail.
    """
    objects = SoftDeleteManager()
    all_objects = models.Manager()  # Access all instances including inactive

    def delete(self, *args, **kwargs):
        """Soft delete: mark as inactive instead of permanently deleting."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])

    class Meta:
        abstract = True

# ============================================================================
# APPEARANCE SETTINGS AND PRESETS
# ============================================================================

APPEARANCE_PRESETS = {
    "aurora": {
        "label": "Aurora Blue",
        "light": {
            "--bg-main": "#f7f8ff",
            "--bg-wash": "#e8f1ff",
            "--bg-sand": "#fff7e7",
            "--brand": "#4c54ff",
            "--brand-dark": "#3d42cc",
            "--brand-contrast": "#ffffff",
            "--ink": "#1b1f2a",
            "--ink-soft": "#5a6478",
            "--line": "#e4e8f0",
            "--panel": "rgba(255, 255, 255, 0.88)",
            "--panel-strong": "#ffffff",
            "--code-bg": "#12182a",
            "--code-text": "#f3f7ff",
            "--blockquote-bg": "#eef5ff",
            "--metric-dark-start": "#11214e",
            "--metric-dark-end": "#253b82",
            "--search-hover-bg": "#f4f8ff",
            "--search-hover-line": "#d8e4fb",
            "--top-strip-bg": "rgba(255, 255, 255, 0.65)",
            "--nav-bg": "rgba(255, 255, 255, 0.95)",
            "--footer-bg": "rgba(255, 255, 255, 0.9)",
        },
        "dark": {
            "--bg-main": "#0d1221",
            "--bg-wash": "#12213f",
            "--bg-sand": "#1a2541",
            "--brand": "#a4b5ff",
            "--brand-dark": "#7c8dff",
            "--brand-contrast": "#04122e",
            "--ink": "#e5ecff",
            "--ink-soft": "#9daac7",
            "--line": "#263556",
            "--panel": "rgba(20, 29, 52, 0.88)",
            "--panel-strong": "#151f36",
            "--code-bg": "#07101f",
            "--code-text": "#d9e8ff",
            "--blockquote-bg": "#182744",
            "--metric-dark-start": "#1f315f",
            "--metric-dark-end": "#2c4a8f",
            "--search-hover-bg": "#172844",
            "--search-hover-line": "#35558c",
            "--top-strip-bg": "rgba(14, 23, 41, 0.75)",
            "--nav-bg": "rgba(11, 19, 34, 0.92)",
            "--footer-bg": "rgba(9, 17, 30, 0.92)",
        },
    },
    "citrus": {
        "label": "Citrus Ember",
        "light": {
            "--bg-main": "#fffaf3",
            "--bg-wash": "#fff0cf",
            "--bg-sand": "#ffe8d8",
            "--brand": "#f59e0b",
            "--brand-dark": "#d97706",
            "--brand-contrast": "#ffffff",
            "--ink": "#2a2118",
            "--ink-soft": "#736457",
            "--line": "#ebdccd",
            "--panel": "rgba(255, 255, 255, 0.9)",
            "--panel-strong": "#ffffff",
            "--code-bg": "#2a1e16",
            "--code-text": "#fff1e5",
            "--blockquote-bg": "#fff0e0",
            "--metric-dark-start": "#8f3c08",
            "--metric-dark-end": "#be5b15",
            "--search-hover-bg": "#fff1e5",
            "--search-hover-line": "#f2cfb0",
            "--top-strip-bg": "rgba(255, 250, 240, 0.8)",
            "--nav-bg": "rgba(255, 252, 247, 0.95)",
            "--footer-bg": "rgba(255, 251, 245, 0.92)",
        },
        "dark": {
            "--bg-main": "#1d1611",
            "--bg-wash": "#2a1d12",
            "--bg-sand": "#302017",
            "--brand": "#fbbf24",
            "--brand-dark": "#f59e0b",
            "--brand-contrast": "#2d1300",
            "--ink": "#ffe8d4",
            "--ink-soft": "#c9ad95",
            "--line": "#4d3829",
            "--panel": "rgba(43, 29, 21, 0.9)",
            "--panel-strong": "#332316",
            "--code-bg": "#140d08",
            "--code-text": "#ffe8d4",
            "--blockquote-bg": "#3a281d",
            "--metric-dark-start": "#7d3408",
            "--metric-dark-end": "#ab4713",
            "--search-hover-bg": "#432f21",
            "--search-hover-line": "#735238",
            "--top-strip-bg": "rgba(27, 19, 14, 0.8)",
            "--nav-bg": "rgba(22, 16, 12, 0.93)",
            "--footer-bg": "rgba(22, 15, 11, 0.93)",
        },
    },
    "evergreen": {
        "label": "Evergreen Mint",
        "light": {
            "--bg-main": "#f4fdf8",
            "--bg-wash": "#ddf6eb",
            "--bg-sand": "#e9fff7",
            "--brand": "#10b981",
            "--brand-dark": "#059669",
            "--brand-contrast": "#ffffff",
            "--ink": "#12261f",
            "--ink-soft": "#4f6c62",
            "--line": "#d6ebe2",
            "--panel": "rgba(255, 255, 255, 0.9)",
            "--panel-strong": "#ffffff",
            "--code-bg": "#11251e",
            "--code-text": "#e7fff6",
            "--blockquote-bg": "#e8fff4",
            "--metric-dark-start": "#155741",
            "--metric-dark-end": "#1f7a5b",
            "--search-hover-bg": "#ebfff6",
            "--search-hover-line": "#b9e7d5",
            "--top-strip-bg": "rgba(243, 255, 250, 0.8)",
            "--nav-bg": "rgba(249, 255, 252, 0.95)",
            "--footer-bg": "rgba(246, 255, 251, 0.92)",
        },
        "dark": {
            "--bg-main": "#0f1d18",
            "--bg-wash": "#112922",
            "--bg-sand": "#153328",
            "--brand": "#3ad3a1",
            "--brand-dark": "#10b981",
            "--brand-contrast": "#032217",
            "--ink": "#d6ffef",
            "--ink-soft": "#95c9b5",
            "--line": "#2d5648",
            "--panel": "rgba(18, 42, 34, 0.9)",
            "--panel-strong": "#16372c",
            "--code-bg": "#0a1612",
            "--code-text": "#dcfff2",
            "--blockquote-bg": "#1a3f31",
            "--metric-dark-start": "#1f6b52",
            "--metric-dark-end": "#2f906f",
            "--search-hover-bg": "#1d4536",
            "--search-hover-line": "#34775f",
            "--top-strip-bg": "rgba(14, 34, 27, 0.82)",
            "--nav-bg": "rgba(13, 30, 24, 0.93)",
            "--footer-bg": "rgba(10, 26, 20, 0.93)",
        },
    },
    "royal": {
        "label": "Royal Magenta",
        "light": {
            "--bg-main": "#fcf6ff",
            "--bg-wash": "#f3e8ff",
            "--bg-sand": "#ffe9f7",
            "--brand": "#7c3aed",
            "--brand-dark": "#6d28d9",
            "--brand-contrast": "#ffffff",
            "--ink": "#221833",
            "--ink-soft": "#685b82",
            "--line": "#e9dcf6",
            "--panel": "rgba(255, 255, 255, 0.9)",
            "--panel-strong": "#ffffff",
            "--code-bg": "#22153a",
            "--code-text": "#f4ebff",
            "--blockquote-bg": "#f4e9ff",
            "--metric-dark-start": "#43207a",
            "--metric-dark-end": "#6a34b5",
            "--search-hover-bg": "#f8f0ff",
            "--search-hover-line": "#d9c3f2",
            "--top-strip-bg": "rgba(251, 245, 255, 0.8)",
            "--nav-bg": "rgba(254, 250, 255, 0.95)",
            "--footer-bg": "rgba(252, 248, 255, 0.92)",
        },
        "dark": {
            "--bg-main": "#171124",
            "--bg-wash": "#211335",
            "--bg-sand": "#2b173e",
            "--brand": "#d8b4fe",
            "--brand-dark": "#a78bfa",
            "--brand-contrast": "#1a0a31",
            "--ink": "#f2e8ff",
            "--ink-soft": "#bda7de",
            "--line": "#4a336d",
            "--panel": "rgba(34, 21, 53, 0.9)",
            "--panel-strong": "#2a1a43",
            "--code-bg": "#0f0920",
            "--code-text": "#f4e9ff",
            "--blockquote-bg": "#30204a",
            "--metric-dark-start": "#56308d",
            "--metric-dark-end": "#7542ba",
            "--search-hover-bg": "#38255a",
            "--search-hover-line": "#6a49a4",
            "--top-strip-bg": "rgba(25, 17, 39, 0.82)",
            "--nav-bg": "rgba(20, 12, 32, 0.93)",
            "--footer-bg": "rgba(20, 12, 32, 0.93)",
        },
    },
}

APPEARANCE_PRESET_CHOICES = [
    (key, payload["label"]) for key, payload in APPEARANCE_PRESETS.items()
]


# ============================================================================
# SINGLETON SETTINGS MODELS (using django-solo)
# ============================================================================


class SiteIdentitySettings(SingletonModel):
    """Site branding and identity (singleton)."""

    site_name = models.CharField(max_length=120, default="Ultimate Blog")
    site_tagline = models.CharField(max_length=180, blank=True)
    admin_brand_name = models.CharField(max_length=120, default="Admin")
    brand_logo_url = models.CharField(
        max_length=320,
        blank=True,
        help_text="Absolute or relative logo URL used for light mode.",
    )
    brand_logo_dark_url = models.CharField(
        max_length=320,
        blank=True,
        help_text="Optional dark-mode logo URL. Falls back to light logo URL.",
    )
    brand_logo_upload = models.FileField(
        upload_to="branding/logos/",
        blank=True,
        help_text="Optional uploaded logo file for light mode.",
    )
    brand_logo_dark_upload = models.FileField(
        upload_to="branding/logos/",
        blank=True,
        help_text="Optional uploaded logo file for dark mode.",
    )
    favicon_url = models.CharField(
        max_length=320,
        blank=True,
        help_text="Absolute or relative favicon URL used for light mode.",
    )
    favicon_dark_url = models.CharField(
        max_length=320,
        blank=True,
        help_text="Optional dark-mode favicon URL. Falls back to light favicon.",
    )
    favicon_upload = models.FileField(
        upload_to="branding/favicons/",
        blank=True,
        help_text="Optional uploaded favicon file for light mode.",
    )
    favicon_dark_upload = models.FileField(
        upload_to="branding/favicons/",
        blank=True,
        help_text="Optional uploaded favicon file for dark mode.",
    )
    default_author_display = models.CharField(max_length=120, blank=True)
    support_email = models.EmailField(blank=True)
    contact_email = models.EmailField(blank=True)
    footer_notice = models.CharField(max_length=220, blank=True)
    legal_company_name = models.CharField(max_length=120, blank=True)
    homepage_cta_label = models.CharField(max_length=40, default="Explore")
    homepage_cta_url = models.CharField(max_length=220, default="/")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Profile"
        verbose_name_plural = "Site Profile"

    def __str__(self):
        return f"Site Profile ({self.site_name})"

    def _asset_url(self, upload_field: str, url_field: str) -> str:
        upload = getattr(self, upload_field, None)
        if upload:
            try:
                return upload.url
            except Exception:
                pass
        return (getattr(self, url_field, "") or "").strip()

    @property
    def resolved_brand_logo_url(self) -> str:
        return self._asset_url("brand_logo_upload", "brand_logo_url")

    @property
    def resolved_brand_logo_dark_url(self) -> str:
        return (
            self._asset_url("brand_logo_dark_upload", "brand_logo_dark_url")
            or self.resolved_brand_logo_url
        )

    @property
    def resolved_favicon_url(self) -> str:
        return (
            self._asset_url("favicon_upload", "favicon_url")
            or self.resolved_brand_logo_url
        )

    @property
    def resolved_favicon_dark_url(self) -> str:
        return (
            self._asset_url("favicon_dark_upload", "favicon_dark_url")
            or self.resolved_favicon_url
            or self.resolved_brand_logo_dark_url
        )


class SeoSettings(SingletonModel):
    """SEO metadata defaults (singleton)."""

    default_meta_title = models.CharField(max_length=70, blank=True)
    default_meta_description = models.CharField(max_length=170, blank=True)
    canonical_base_url = models.URLField(blank=True)
    robots_index = models.BooleanField(default=True)
    robots_follow = models.BooleanField(default=True)
    enable_open_graph = models.BooleanField(default=True)
    enable_twitter_cards = models.BooleanField(default=True)
    default_og_image_url = models.URLField(blank=True)
    twitter_site_handle = models.CharField(max_length=40, blank=True)
    organization_schema_name = models.CharField(max_length=120, blank=True)
    organization_schema_url = models.URLField(blank=True)
    google_site_verification = models.CharField(max_length=180, blank=True)
    bing_site_verification = models.CharField(max_length=180, blank=True)
    yandex_site_verification = models.CharField(max_length=180, blank=True)
    pinterest_site_verification = models.CharField(max_length=180, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SEO Settings"
        verbose_name_plural = "SEO Settings"

    def __str__(self):
        return "SEO Settings"


class IntegrationSettings(SingletonModel):
    """Analytics and third-party integrations (singleton)."""

    class AnalyticsProvider(models.TextChoices):
        NONE = "none", "None"
        GA4 = "ga4", "Google Analytics 4"
        GTM = "gtm", "Google Tag Manager"
        PLAUSIBLE = "plausible", "Plausible"
        CUSTOM = "custom", "Custom"

    analytics_provider = models.CharField(
        max_length=20,
        choices=AnalyticsProvider.choices,
        default=AnalyticsProvider.NONE,
    )
    ga4_measurement_id = models.CharField(max_length=40, blank=True)
    gtm_container_id = models.CharField(max_length=40, blank=True)
    plausible_domain = models.CharField(max_length=120, blank=True)
    custom_analytics_snippet = models.TextField(blank=True)
    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=160, blank=True)
    smtp_sender_name = models.CharField(max_length=120, blank=True)
    smtp_sender_email = models.EmailField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integrations"
        verbose_name_plural = "Integrations"

    def __str__(self):
        return "Integrations"


class FeatureControlSettings(SingletonModel):
    """Feature toggles and capability flags (singleton)."""

    enable_newsletter = models.BooleanField(default=True)
    enable_reactions = models.BooleanField(default=True)
    enable_comments = models.BooleanField(default=True)
    moderate_comments = models.BooleanField(default=False)
    comment_spam_threshold = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Algorithmic moderation threshold (1-100). Higher is stricter.",
    )
    enable_quick_preview = models.BooleanField(default=True)
    enable_public_api = models.BooleanField(default=True)
    enable_policy_pages = models.BooleanField(default=True)
    enable_sitemap = models.BooleanField(default=True)
    enable_user_registration = models.BooleanField(default=False)
    enable_auto_tagging = models.BooleanField(default=True)
    auto_tagging_max_tags = models.PositiveSmallIntegerField(default=6)
    auto_tagging_max_total_tags = models.PositiveSmallIntegerField(default=12)
    auto_tagging_max_categories = models.PositiveSmallIntegerField(default=3)
    category_max_depth = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Maximum allowed depth for category paths (e.g. a/b/c = depth 3).",
    )
    auto_tagging_min_score = models.FloatField(default=1.2)
    maintenance_mode = models.BooleanField(default=False)
    read_only_mode = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Feature Controls"
        verbose_name_plural = "Feature Controls"

    def __str__(self):
        return "Feature Controls"


class SiteAppearanceSettings(SingletonModel):
    """Theme and appearance settings (singleton)."""

    class Mode(models.TextChoices):
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.LIGHT)
    preset = models.CharField(
        max_length=40,
        choices=APPEARANCE_PRESET_CHOICES,
        default="aurora",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Appearance Studio"
        verbose_name_plural = "Appearance Studio"

    def __str__(self):
        return f"Appearance Studio ({self.get_mode_display()} - {self.get_preset_display()})"

    @property
    def preset_payload(self):
        return APPEARANCE_PRESETS.get(self.preset, APPEARANCE_PRESETS["aurora"])

    @property
    def css_variables(self):
        mode_key = self.mode if self.mode in {"light", "dark"} else "light"
        return self.preset_payload[mode_key]


class UserProfile(models.Model):
    """Unified user profile for frontend and admin users."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=120, blank=True)
    bio = models.CharField(max_length=320, blank=True)
    avatar_url = models.URLField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    website_url = models.URLField(blank=True)
    timezone = models.CharField(max_length=64, blank=True, default="UTC")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"Profile ({self.effective_name})"

    @property
    def effective_name(self):
        if self.display_name:
            return self.display_name
        full_name = (self.user.get_full_name() or "").strip()
        if full_name:
            return full_name
        return self.user.username

    @classmethod
    def get_for_user(cls, user):
        profile, _ = cls.objects.get_or_create(user=user)
        return profile
