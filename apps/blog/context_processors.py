from __future__ import annotations

import subprocess
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from core.models import (
    FeatureControlSettings,
    IntegrationSettings,
    SeoSettings,
    SiteAppearanceSettings,
    SiteIdentitySettings,
    UserProfile,
)
from comments.models import Comment, NewsletterSubscriber
from .models import (
    ContentRefreshSettings,
    Post,
)


SITE_STATS_CACHE_KEY = "blog_site_stats_v1"
ADMIN_OVERVIEW_CACHE_KEY = "blog_admin_overview_v2"
ADMIN_REPO_OVERVIEW_CACHE_KEY = "blog_admin_repo_overview_v1"
ADMIN_NAV_BADGES_CACHE_KEY = "blog_admin_nav_badges_v1"
EXCLUDED_PATH_PARTS = {".venv", "__pycache__", ".git", "media", "staticfiles"}


def _iter_project_files(root: Path):
    if not root.exists():
        return
    for file in root.rglob("*"):
        if not file.is_file():
            continue
        if any(part in EXCLUDED_PATH_PARTS for part in file.parts):
            continue
        yield file


def _count_files(root: Path, suffixes: set[str]):
    count = 0
    for file in _iter_project_files(root) or []:
        if file.suffix in suffixes:
            count += 1
    return count


def _count_lines(root: Path, suffixes: set[str]):
    total = 0
    for file in _iter_project_files(root) or []:
        if file.suffix not in suffixes:
            continue
        try:
            with file.open("r", encoding="utf-8", errors="ignore") as handle:
                total += sum(1 for _ in handle)
        except OSError:
            continue
    return total


def _safe_git_value(base_dir: Path, args: list[str], fallback: str = "N/A"):
    try:
        return subprocess.check_output(
            ["git", "-C", str(base_dir), *args],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
    except Exception:
        return fallback


def _safe_reverse(name: str, *, args: list | None = None):
    try:
        return reverse(name, args=args or [])
    except Exception:
        return ""


def _count_migration_files(root: Path):
    count = 0
    for file in _iter_project_files(root) or []:
        if file.suffix != ".py":
            continue
        if file.name == "__init__.py":
            continue
        if "migrations" in file.parts:
            count += 1
    return count


def _build_repo_overview(base_dir: Path):
    cached = cache.get(ADMIN_REPO_OVERVIEW_CACHE_KEY)
    if cached is not None:
        return cached

    git_available = (base_dir / ".git").exists()
    code_suffixes = {".py", ".html", ".css", ".js"}
    repo = {
        "git_available": git_available,
        "branch": _safe_git_value(base_dir, ["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": _safe_git_value(base_dir, ["rev-parse", "--short", "HEAD"]),
        "dirty": bool(_safe_git_value(base_dir, ["status", "--porcelain"], fallback="")),
        "python_files": _count_files(base_dir, {".py"}),
        "template_files": _count_files(base_dir / "templates", {".html"}),
        "static_files": _count_files(base_dir / "static", {".css", ".js"}),
        "migration_files": _count_migration_files(base_dir / "apps"),
        "code_lines": _count_lines(base_dir, code_suffixes),
    }
    cache.set(ADMIN_REPO_OVERVIEW_CACHE_KEY, repo, 900)
    return repo


def _build_health_signals(*, site: dict, seo: dict, repo: dict, refresh: dict):
    signals = []

    if site["comments_pending"] > 0:
        signals.append(
            {
                "level": "warning",
                "title": "Pending moderation queue",
                "detail": f"{site['comments_pending']} comments need review.",
                "url": _safe_reverse("blog:admin_comments_list"),
                "action_label": "Open comments",
            }
        )

    if site["posts_draft"] > 0:
        signals.append(
            {
                "level": "info",
                "title": "Draft backlog present",
                "detail": f"{site['posts_draft']} drafts are waiting for publishing decisions.",
                "url": _safe_reverse("blog:admin_posts_list"),
                "action_label": "Review drafts",
            }
        )

    if seo:
        critical_open = seo.get("issue_counts", {}).get("critical_open", 0)
        pending_total = seo.get("suggestion_counts", {}).get("pending_total", 0)
        if critical_open > 0:
            signals.append(
                {
                    "level": "danger",
                    "title": "Critical SEO issues detected",
                    "detail": f"{critical_open} critical issues are still open.",
                    "url": _safe_reverse(
                        "admin_config:seo_control_canonical_section",
                        args=["results"],
                    ),
                    "action_label": "Inspect issues",
                }
            )
        elif pending_total > 0:
            signals.append(
                {
                    "level": "info",
                    "title": "SEO queue needs decisions",
                    "detail": f"{pending_total} SEO suggestions are pending review.",
                    "url": _safe_reverse(
                        "admin_config:seo_control_canonical_section",
                        args=["onsite"],
                    ),
                    "action_label": "Open queue",
                }
            )

    if repo.get("dirty"):
        signals.append(
            {
                "level": "warning",
                "title": "Repository has uncommitted changes",
                "detail": "Working tree is dirty; validate deployment readiness before release.",
                "url": "",
                "action_label": "",
            }
        )

    if not refresh.get("enabled"):
        signals.append(
            {
                "level": "info",
                "title": "Content refresh automation disabled",
                "detail": "Automated refresh is currently off for posts and pages.",
                "url": _safe_reverse("admin:blog_contentrefreshsettings_change", args=[1]),
                "action_label": "Configure timer",
            }
        )

    return signals


def _build_admin_overview():
    published_qs = Post.objects.published()
    window_start = timezone.now() - timedelta(days=7)
    comments_total = Comment.objects.count()
    posts_published = published_qs.count()
    views_total = (
        published_qs.aggregate(total_views=Sum("views_count")).get("total_views") or 0
    )

    tag_total = 0
    topic_total = 0
    category_total = 0
    try:
        tag_total = Post.tags.tag_model.objects.count()
        topic_total = Post.primary_topic.tag_model.objects.count()
        category_total = Post.categories.tag_model.objects.count()
    except Exception:
        pass

    top_posts = list(
        published_qs.order_by("-views_count", "-published_at")
        .values("id", "title", "views_count", "published_at")[:6]
    )
    recent_posts = list(
        Post.objects.order_by("-updated_at")
        .values("id", "title", "status", "updated_at")[:6]
    )

    base_dir = settings.BASE_DIR
    refresh_timer = ContentRefreshSettings.get_solo()
    appearance_settings = SiteAppearanceSettings.get_solo()
    repo_overview = _build_repo_overview(base_dir)
    seo = {}
    try:
        from seo.services import seo_overview_metrics

        seo = seo_overview_metrics()
    except Exception:
        seo = {}
    posts_total = Post.objects.count()
    draft_posts = Post.objects.filter(status=Post.Status.DRAFT).count()
    publication_rate = round((posts_published / posts_total) * 100, 1) if posts_total else 0
    pending_comment_rate = (
        round((Comment.objects.filter(is_approved=False).count() / comments_total) * 100, 1)
        if comments_total
        else 0
    )
    latest_seo_score = seo.get("latest_score") if seo else None
    if latest_seo_score is None:
        seo_health = {"label": "No audits", "tone": "secondary"}
    elif latest_seo_score >= 80:
        seo_health = {"label": "Healthy", "tone": "success"}
    elif latest_seo_score >= 60:
        seo_health = {"label": "Needs attention", "tone": "warning"}
    else:
        seo_health = {"label": "At risk", "tone": "danger"}

    content_refresh = {
        "enabled": refresh_timer.auto_refresh_enabled,
        "post_interval_hours": refresh_timer.post_refresh_interval_hours,
        "page_interval_hours": refresh_timer.page_refresh_interval_hours,
        "max_items_per_run": refresh_timer.max_items_per_run,
        "last_run_at": refresh_timer.last_run_at,
    }
    site = {
        "posts_total": posts_total,
        "posts_published": posts_published,
        "posts_draft": draft_posts,
        "comments_total": comments_total,
        "comments_pending": Comment.objects.filter(is_approved=False).count(),
        "subscribers_total": NewsletterSubscriber.objects.filter(is_active=True).count(),
        "tags_total": tag_total,
        "topics_total": topic_total,
        "categories_total": category_total,
        "views_total": views_total,
    }
    overview = {
        "updated_at": timezone.now(),
        "site": site,
        "insights": {
            "posts_created_7d": Post.objects.filter(created_at__gte=window_start).count(),
            "posts_published_7d": Post.objects.filter(
                status=Post.Status.PUBLISHED,
                published_at__gte=window_start,
            ).count(),
            "comments_7d": Comment.objects.filter(created_at__gte=window_start).count(),
            "active_authors_7d": Post.objects.filter(created_at__gte=window_start)
            .values("author_id")
            .distinct()
            .count(),
            "avg_comments_per_post": round(comments_total / posts_published, 2)
            if posts_published
            else 0,
            "avg_views_per_post": round(views_total / posts_published, 1)
            if posts_published
            else 0,
        },
        "repo": repo_overview,
        "content_refresh": content_refresh,
        "appearance": {
            "mode": appearance_settings.mode,
            "mode_label": appearance_settings.get_mode_display(),
            "preset": appearance_settings.preset,
            "preset_label": appearance_settings.get_preset_display(),
        },
        "seo": seo,
        "derived": {
            "publication_rate": publication_rate,
            "pending_comment_rate": pending_comment_rate,
            "seo_health": seo_health,
        },
        "top_posts": top_posts,
        "recent_posts": recent_posts,
    }
    overview["health_signals"] = _build_health_signals(
        site=site,
        seo=seo,
        repo=repo_overview,
        refresh=content_refresh,
    )
    return overview


def _build_admin_nav_badges():
    payload = {
        "pending_comments": Comment.objects.filter(is_approved=False).count(),
        "seo_pending_total": 0,
    }
    try:
        from seo.models import SeoSuggestion

        payload["seo_pending_total"] = SeoSuggestion.objects.filter(
            status=SeoSuggestion.Status.PENDING
        ).count()
    except Exception:
        payload["seo_pending_total"] = 0
    return payload


def get_admin_nav_badges_payload():
    payload = cache.get(ADMIN_NAV_BADGES_CACHE_KEY)
    if payload is None:
        payload = _build_admin_nav_badges()
        cache.set(ADMIN_NAV_BADGES_CACHE_KEY, payload, 30)
    return payload


def invalidate_admin_nav_badges_cache() -> None:
    cache.delete(ADMIN_NAV_BADGES_CACHE_KEY)


def site_stats(request):
    stats = cache.get(SITE_STATS_CACHE_KEY)
    if stats is None:
        published_qs = Post.objects.published()
        stats = {
            "site_total_posts": published_qs.count(),
            "site_total_authors": Post.objects.values("author_id").distinct().count(),
            "site_total_subscribers": NewsletterSubscriber.objects.filter(
                is_active=True
            ).count(),
        }
        cache.set(SITE_STATS_CACHE_KEY, stats, 60)
    return stats


def admin_overview(request):
    if not request.path.startswith("/admin"):
        return {}
    if not (request.user.is_authenticated and request.user.is_staff):
        return {}
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match and resolver_match.view_name != "admin:index":
        return {}

    overview = cache.get(ADMIN_OVERVIEW_CACHE_KEY)
    if overview is None:
        overview = _build_admin_overview()
        cache.set(ADMIN_OVERVIEW_CACHE_KEY, overview, 120)

    return {"admin_overview": overview}


def admin_nav_badges(request):
    if not request.path.startswith("/admin"):
        return {}
    if not (request.user.is_authenticated and request.user.is_staff):
        return {}
    return {"admin_nav_badges": get_admin_nav_badges_payload()}


def site_appearance(request):
    appearance = SiteAppearanceSettings.get_solo()
    identity = SiteIdentitySettings.get_solo()
    seo_defaults = SeoSettings.get_solo()
    integrations = IntegrationSettings.get_solo()
    controls = FeatureControlSettings.get_solo()
    css_variables = appearance.css_variables
    current_user_profile = {}
    if request.user.is_authenticated:
        try:
            profile = UserProfile.get_for_user(request.user)
            current_user_profile = {
                "display_name": profile.display_name,
                "effective_name": profile.effective_name,
                "bio": profile.bio,
                "avatar_url": profile.avatar_url,
                "location": profile.location,
                "website_url": profile.website_url,
                "timezone": profile.timezone,
            }
        except Exception:
            current_user_profile = {}

    return {
        "site_appearance": {
            "mode": appearance.mode,
            "preset": appearance.preset,
            "mode_label": appearance.get_mode_display(),
            "preset_label": appearance.get_preset_display(),
            "updated_at": appearance.updated_at.isoformat() if appearance.updated_at else "",
            "css_variables": css_variables,
            "theme_color": css_variables.get("--bg-main"),
        },
        "site_identity": {
            "site_name": identity.site_name,
            "site_tagline": identity.site_tagline,
            "admin_brand_name": identity.admin_brand_name,
            "brand_logo_url": identity.resolved_brand_logo_url,
            "brand_logo_dark_url": identity.resolved_brand_logo_dark_url,
            "favicon_url": identity.resolved_favicon_url,
            "favicon_dark_url": identity.resolved_favicon_dark_url,
            "default_author_display": identity.default_author_display,
            "support_email": identity.support_email,
            "contact_email": identity.contact_email,
            "footer_notice": identity.footer_notice,
            "legal_company_name": identity.legal_company_name,
            "homepage_cta_label": identity.homepage_cta_label,
            "homepage_cta_url": identity.homepage_cta_url,
        },
        "site_verification": {
            "google": seo_defaults.google_site_verification,
            "bing": seo_defaults.bing_site_verification,
            "yandex": seo_defaults.yandex_site_verification,
            "pinterest": seo_defaults.pinterest_site_verification,
        },
        "site_seo_flags": {
            "enable_open_graph": seo_defaults.enable_open_graph,
            "enable_twitter_cards": seo_defaults.enable_twitter_cards,
            "organization_schema_name": seo_defaults.organization_schema_name,
            "organization_schema_url": seo_defaults.organization_schema_url,
        },
        "site_integrations": {
            "analytics_provider": integrations.analytics_provider,
            "ga4_measurement_id": integrations.ga4_measurement_id,
            "gtm_container_id": integrations.gtm_container_id,
            "plausible_domain": integrations.plausible_domain,
            "custom_analytics_snippet": integrations.custom_analytics_snippet,
            "webhook_url": integrations.webhook_url,
            "webhook_secret": integrations.webhook_secret,
            "smtp_sender_name": integrations.smtp_sender_name,
            "smtp_sender_email": integrations.smtp_sender_email,
        },
        "feature_controls": {
            "enable_newsletter": controls.enable_newsletter,
            "enable_reactions": controls.enable_reactions,
            "enable_comments": controls.enable_comments,
            "moderate_comments": controls.moderate_comments,
            "comment_spam_threshold": controls.comment_spam_threshold,
            "enable_quick_preview": controls.enable_quick_preview,
            "enable_public_api": controls.enable_public_api,
            "enable_policy_pages": controls.enable_policy_pages,
            "enable_sitemap": controls.enable_sitemap,
            "enable_user_registration": controls.enable_user_registration,
            "enable_auto_tagging": controls.enable_auto_tagging,
            "auto_tagging_max_tags": controls.auto_tagging_max_tags,
            "auto_tagging_max_total_tags": controls.auto_tagging_max_total_tags,
            "auto_tagging_max_categories": controls.auto_tagging_max_categories,
            "category_max_depth": getattr(controls, "category_max_depth", 5),
            "auto_tagging_min_score": controls.auto_tagging_min_score,
            "maintenance_mode": controls.maintenance_mode,
            "read_only_mode": controls.read_only_mode,
        },
        "current_user_profile": current_user_profile,
    }
