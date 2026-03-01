"""
Django settings for config project - Development Configuration.
"""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "*.local"]

# Internal IPs — required by debug toolbar and INTERNAL_IPS-gated features
INTERNAL_IPS = ["127.0.0.1", "::1"]

# Database configuration from base.py - respects environment variables
# No fallback values here - must be set in .env file

# Security settings relaxed for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# Email backend for development (console output)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Django shell plus
SHELL_PLUS_IMPORTS = [
    "from django.contrib.auth.models import User",
]

# django-debug-toolbar — only when package is installed
try:
    import debug_toolbar  # noqa: F401  # type: ignore[import-untyped]
    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE = [
        "django.middleware.security.SecurityMiddleware",
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "seo.middleware.SeoRedirectMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "core.middleware.PlatformGuardMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django_htmx.middleware.HtmxMiddleware",
        "blog.middleware.ContentDateRefreshMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ]
except ImportError:
    pass  # debug_toolbar not installed — silently skip
