"""
Django settings for config project - Production Configuration.
"""

import logging
import os
from importlib.util import find_spec
from pathlib import Path

from .base import *  # noqa: F403

logger = logging.getLogger(__name__)

PROJECT_BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEBUG = False
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "example.com").split(",")

# SECRET_KEY is already enforced in base.py - no fallback here

# Production database — supports Render/Heroku DATABASE_URL or individual POSTGRES_* vars
_DATABASE_URL = os.getenv("DATABASE_URL", "")

if _DATABASE_URL:
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    import dj_database_url

    # Strip query params that dj-database-url doesn't handle (e.g. channel_binding)
    _parsed = urlparse(_DATABASE_URL)
    _clean_qs = {k: v for k, v in parse_qs(_parsed.query).items() if k == "sslmode"}
    _clean_url = urlunparse(_parsed._replace(query=urlencode(_clean_qs, doseq=True)))

    DATABASES = {
        "default": dj_database_url.config(
            default=_clean_url,
            conn_max_age=int(os.getenv("POSTGRES_CONN_MAX_AGE", "600")),
            conn_health_checks=True,
            ssl_require=os.getenv("DATABASE_SSL", "true").lower() == "true",
        )
    }
    DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 10
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
            "HOST": os.getenv("POSTGRES_HOST"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "600")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "connect_timeout": 10,
            },
        }
    }

# Security settings enabled for production
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Use cache-backed sessions in production for performance.
# Requires a configured CACHES backend (Redis configured below).
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# Static files — whitenoise serves compressed, fingerprinted assets from collectstatic output.
# Media storage — conditional S3 when USE_S3 is set, otherwise local filesystem.
_USE_S3 = os.getenv("USE_S3", "").lower() in ("true", "1", "yes")

if _USE_S3:
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_CUSTOM_DOMAIN = os.getenv(
        "AWS_S3_CUSTOM_DOMAIN",
        f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com" if AWS_STORAGE_BUCKET_NAME else None,
    )
    AWS_DEFAULT_ACL = None  # Use bucket-level ACL
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_QUERYSTRING_AUTH = False

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/" if AWS_S3_CUSTOM_DOMAIN else "/media/"
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# Override MIDDLEWARE to insert WhiteNoise right after SecurityMiddleware.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # must be immediately after Security
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

# Email backend for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

# Logging for production — dual output: file + stdout (containers)
LOG_DIR = PROJECT_BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FORMATTERS: dict = {
    "verbose": {
        "format": "{asctime} {levelname} {name} {message}",
        "style": "{",
    },
}

# Structured JSON logging when python-json-logger is available
if find_spec("pythonjsonlogger"):
    _LOG_FORMATTERS["json"] = {
        "()": "pythonjsonlogger.json.JsonFormatter",
        "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
    }
    _CONSOLE_FORMATTER = "json"
else:
    _CONSOLE_FORMATTER = "verbose"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": _LOG_FORMATTERS,
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": _CONSOLE_FORMATTER,
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "django.log"),
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Cache configuration for production.
# Falls back to local-memory cache if django-redis isn't installed in this env.
if not find_spec("django_redis"):
    raise ImportError(
        "django-redis is required in production. "
        "Install it with: pip install django-redis"
    )

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ── Sentry error tracking ───────────────────────────────────────────────────
_SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if _SENTRY_DSN and find_spec("sentry_sdk"):
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        release=os.getenv("SENTRY_RELEASE", ""),
    )
    logger.info("Sentry initialised (dsn=***%s)", _SENTRY_DSN[-8:])
elif _SENTRY_DSN:
    logger.warning("SENTRY_DSN is set but sentry-sdk is not installed — skipping.")
