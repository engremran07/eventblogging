from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone

from .content_refresh import run_content_date_refresh
from .models import ContentRefreshSettings


class ContentDateRefreshMiddleware:
    CHECK_EVERY_SECONDS = 300
    CACHE_KEY = "blog_content_refresh_last_check_v1"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._maybe_run_refresh()
        return self.get_response(request)

    def _maybe_run_refresh(self):
        now = timezone.now()
        last_check = cache.get(self.CACHE_KEY)
        if last_check and (now - last_check).total_seconds() < self.CHECK_EVERY_SECONDS:
            return

        cache.set(self.CACHE_KEY, now, self.CHECK_EVERY_SECONDS)

        settings = ContentRefreshSettings.get_solo()
        if not settings.auto_refresh_enabled:
            return

        run_content_date_refresh(force=False, now=now)
