from __future__ import annotations

from django.core.cache import cache
from django.db import models
from django.http import HttpResponseGone, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.urls import Resolver404, resolve
from django.utils import timezone

from .models import SeoRedirectRule


class SeoRedirectMiddleware:
    CACHE_KEY_PREFIX = "seo_redirect_rule_v1"
    CACHE_TIMEOUT = 120

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/") or request.path.startswith("/static/"):
            return self.get_response(request)

        rule = self._get_rule(request.path)
        if rule is not None and rule.is_active:
            if (
                rule.status_code == SeoRedirectRule.StatusCode.GONE
                and self._has_live_content_path(request.path)
            ):
                self._deactivate_rule(rule.id, request.path)
                return self.get_response(request)

            self._touch_rule(rule.id)
            if rule.status_code == SeoRedirectRule.StatusCode.GONE:
                return HttpResponseGone("This URL is no longer available.")
            if rule.target_url and rule.target_url != request.path:
                if rule.status_code == SeoRedirectRule.StatusCode.FOUND:
                    return HttpResponseRedirect(rule.target_url)
                return HttpResponsePermanentRedirect(rule.target_url)

        return self.get_response(request)

    def _get_rule(self, path: str):
        cache_key = f"{self.CACHE_KEY_PREFIX}:{path}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        rule = SeoRedirectRule.objects.filter(old_path=path, is_active=True).first()
        cache.set(cache_key, rule, self.CACHE_TIMEOUT)
        return rule

    def _touch_rule(self, rule_id: int):
        SeoRedirectRule.objects.filter(pk=rule_id).update(
            hits=models.F("hits") + 1,
            last_hit_at=timezone.now(),
        )

    def _deactivate_rule(self, rule_id: int, path: str):
        SeoRedirectRule.objects.filter(pk=rule_id).update(
            is_active=False,
            notes="Auto-disabled because live content is available at this path.",
        )
        cache.set(f"{self.CACHE_KEY_PREFIX}:{path}", None, self.CACHE_TIMEOUT)

    def _has_live_content_path(self, path: str) -> bool:
        try:
            match = resolve(path)
        except Resolver404:
            return False

        view_name = (match.view_name or "").strip()
        slug = (match.kwargs or {}).get("slug")
        if not slug:
            return False

        # Lazy imports avoid circular app loading on startup.
        if view_name == "blog:post_detail":
            from blog.models import Post

            return Post.objects.filter(
                slug=slug,
                status=Post.Status.PUBLISHED,
                published_at__isnull=False,
                published_at__lte=timezone.now(),
            ).exists()

        if view_name == "pages:detail":
            from pages.models import Page

            return Page.objects.filter(
                slug=slug,
                status=Page.Status.PUBLISHED,
                published_at__isnull=False,
                published_at__lte=timezone.now(),
            ).exists()

        return False
