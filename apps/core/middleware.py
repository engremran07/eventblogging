from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .utils import cache_feature_control_settings


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
AUTH_ALLOWED_PREFIXES = (
    "/auth/login/",
    "/auth/logout/",
    "/auth/password-change/",
    "/auth/password-reset/",
    "/admin/login/",
    "/admin/logout/",
)
ALWAYS_ALLOWED_PREFIXES = ("/static/", "/media/", "/favicon.ico")


class PlatformGuardMiddleware:
    """
    Enforce platform-level kill switches from FeatureControlSettings.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        controls = cache_feature_control_settings()
        request.feature_controls = controls  # type: ignore[attr-defined]

        if self._is_maintenance_blocked(request, controls):
            return self._maintenance_response(request)

        if self._is_read_only_blocked(request, controls):
            return HttpResponse("Platform is in read-only mode.", status=503)

        return self.get_response(request)

    def _is_exempt(self, request: HttpRequest) -> bool:
        path = request.path or "/"
        if path.startswith(ALWAYS_ALLOWED_PREFIXES):
            return True
        if path.startswith(AUTH_ALLOWED_PREFIXES):
            return True
        return False

    def _is_staff(self, request: HttpRequest) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_staff)

    def _is_maintenance_blocked(self, request: HttpRequest, controls: object) -> bool:
        if not getattr(controls, "maintenance_mode", False):
            return False
        if self._is_exempt(request):
            return False
        if self._is_staff(request):
            return False
        return True

    def _is_read_only_blocked(self, request: HttpRequest, controls: object) -> bool:
        if not getattr(controls, "read_only_mode", False):
            return False
        if request.method in SAFE_METHODS:
            return False
        if self._is_exempt(request):
            return False
        if self._is_staff(request):
            return False
        return True

    def _maintenance_response(self, request: HttpRequest) -> HttpResponse:
        if request.headers.get("HX-Request") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return HttpResponse("Platform maintenance in progress.", status=503)
        return render(request, "maintenance.html", status=503)
