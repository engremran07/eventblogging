"""
Django settings for config project - Development Configuration.
"""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "*.local"]

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
