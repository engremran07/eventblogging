from __future__ import annotations

from datetime import date, datetime, time

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

from blog.models import Post
from core.models import FeatureControlSettings
from pages.models import Page
from pages.policies import POLICY_PAGES, POLICY_SLUGS


def _feature_controls():
    try:
        return FeatureControlSettings.get_solo()
    except Exception:
        return None


def _sitemap_enabled():
    controls = _feature_controls()
    if controls is None:
        return True
    return bool(controls.enable_sitemap)


def _policy_pages_enabled():
    controls = _feature_controls()
    if controls is None:
        return True
    return bool(controls.enable_policy_pages)


def _static_routes():
    routes = [
        ("blog:home", "daily", 1.0),
        ("pages:list", "weekly", 0.8),
    ]
    if _policy_pages_enabled():
        routes.append(("pages:policy_index", "weekly", 0.7))
    return routes


def _as_aware_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    if isinstance(value, date):
        dt = datetime.combine(value, time.min)
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return None


def _latest_content_lastmod():
    latest_post = (
        Post.objects.published()
        .order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    latest_page = (
        Page.objects.published()
        .order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    latest_policy = None
    if _policy_pages_enabled():
        latest_policy = max((policy["updated_at"] for policy in POLICY_PAGES), default=None)

    candidates = [
        _as_aware_datetime(latest_post),
        _as_aware_datetime(latest_page),
        _as_aware_datetime(latest_policy),
    ]
    candidates = [candidate for candidate in candidates if candidate is not None]
    if not candidates:
        return timezone.now()
    return max(candidates)


def _policy_sitemap_items():
    if not _policy_pages_enabled():
        return []

    overrides = dict(
        Page.objects.published()
        .filter(slug__in=POLICY_SLUGS)
        .values_list("slug", "updated_at")
    )

    return [
        {
            "slug": policy["slug"],
            "updated_at": overrides.get(policy["slug"], policy["updated_at"]),
        }
        for policy in POLICY_PAGES
    ]


class BlogPostSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        if not _sitemap_enabled():
            return []
        return Post.objects.published().order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at


class PageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        if not _sitemap_enabled():
            return []
        return Page.objects.published().order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        if not _sitemap_enabled():
            return []
        return [name for name, _changefreq, _priority in _static_routes()]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return _latest_content_lastmod()


class PolicySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        if not _sitemap_enabled():
            return []
        return _policy_sitemap_items()

    def location(self, item):
        return reverse("pages:policy_detail", kwargs={"slug": item["slug"]})

    def lastmod(self, item):
        return _as_aware_datetime(item.get("updated_at"))


class UnifiedSitemap(Sitemap):
    limit = 50000

    def items(self):
        if not _sitemap_enabled():
            return []

        latest_lastmod = _latest_content_lastmod()
        items = [
            {
                "location": reverse(route_name),
                "lastmod": latest_lastmod,
                "changefreq": changefreq,
                "priority": priority,
            }
            for route_name, changefreq, priority in _static_routes()
        ]

        items.extend(
            {
                "location": post.get_absolute_url(),
                "lastmod": post.updated_at,
                "changefreq": "daily",
                "priority": 0.8,
            }
            for post in Post.objects.published().order_by("-updated_at")
        )

        items.extend(
            {
                "location": page.get_absolute_url(),
                "lastmod": page.updated_at,
                "changefreq": "weekly",
                "priority": 0.7,
            }
            for page in Page.objects.published().order_by("-updated_at")
        )

        if _policy_pages_enabled():
            items.extend(
                {
                    "location": reverse(
                        "pages:policy_detail",
                        kwargs={"slug": policy_item["slug"]},
                    ),
                    "lastmod": _as_aware_datetime(policy_item["updated_at"]),
                    "changefreq": "monthly",
                    "priority": 0.5,
                }
                for policy_item in _policy_sitemap_items()
            )

        now = timezone.now()
        items.sort(
            key=lambda item: _as_aware_datetime(item.get("lastmod")) or now,
            reverse=True,
        )
        return items

    def location(self, item):
        return item["location"]

    def lastmod(self, item):
        return _as_aware_datetime(item.get("lastmod"))

    def changefreq(self, item):
        return item.get("changefreq")

    def priority(self, item):
        return item.get("priority")


section_sitemaps = {
    "static": StaticViewSitemap,
    "posts": BlogPostSitemap,
    "pages": PageSitemap,
    "policies": PolicySitemap,
}

unified_sitemaps = {"all": UnifiedSitemap}
