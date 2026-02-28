"""
Django settings for config project - Base configuration.
This module contains all shared settings used across all environments.
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    import dotenv
    dotenv.load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
except ImportError:
    pass  # python-dotenv not installed, fallback to system env vars

# Add apps directory to Python path for direct imports (blog, seo, etc.)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'apps'))


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def env_session_samesite(name: str, default: str = "Lax") -> str:
    value = (os.getenv(name) or default).strip().lower()
    allowed = {
        "lax": "Lax",
        "strict": "Strict",
        "none": "None",
    }
    return allowed.get(value, default)


# ⚠️ CRITICAL: SECRET_KEY MUST be provided via environment variable
# Never use default/fallback values in production
if "DJANGO_SECRET_KEY" not in os.environ:
    raise ValueError(
        "DJANGO_SECRET_KEY environment variable is required. "
        "Generate one with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# DEBUG must be explicitly set; defaults to False for safety
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

PROD_DEFAULT = not DEBUG
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", PROD_DEFAULT)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", PROD_DEFAULT)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", PROD_DEFAULT)
SESSION_ENGINE = os.getenv("DJANGO_SESSION_ENGINE", "django.contrib.sessions.backends.db")
SESSION_COOKIE_NAME = os.getenv("DJANGO_SESSION_COOKIE_NAME", "djangoblog_sessionid")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env_session_samesite("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_COOKIE_AGE", 60 * 60 * 24 * 14)
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool(
    "DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE",
    False,
)
SESSION_SAVE_EVERY_REQUEST = env_bool("DJANGO_SESSION_SAVE_EVERY_REQUEST", False)
SESSION_MARKER_PREFIX = os.getenv("DJANGO_SESSION_MARKER_PREFIX", "djangoblog")
SECURE_HSTS_SECONDS = int(
    os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000" if PROD_DEFAULT else "0")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", PROD_DEFAULT
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", PROD_DEFAULT)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.postgres",
    "django_htmx",
    "tagulous",
    "solo",
    "core",
    "blog",
    "comments",
    "tags",
    "seo",
    "pages",
]

TEST_RUNNER = "config.test_runner.FirstPartyDiscoverRunner"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "blog.context_processors.site_stats",
                "blog.context_processors.site_appearance",
                "blog.context_processors.admin_overview",
                "blog.context_processors.admin_nav_badges",
                "pages.context_processors.navigation_pages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ⚠️ CRITICAL: Database credentials MUST come from environment variables
# Never use default/hardcoded credentials
required_db_vars = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST"]
for var in required_db_vars:
    if var not in os.environ:
        raise ValueError(
            f"{var} environment variable is required. Check .env.example for configuration."
        )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),  # Safe default for host only
        "PORT": os.getenv("POSTGRES_PORT", "5432"),  # Safe default for port only
        "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "blog:dashboard"
LOGOUT_REDIRECT_URL = "blog:home"

SERIALIZATION_MODULES = {
    "xml": "tagulous.serializers.xml_serializer",
    "json": "tagulous.serializers.json",
    "python": "tagulous.serializers.python",
    "yaml": "tagulous.serializers.pyyaml",
}

TAGULOUS_DEFAULT_TAG_OPTIONS = {
    "force_lowercase": True,
    "autocomplete_limit": 30,
}

TAGULOUS_AUTOCOMPLETE_SETTINGS = {
    "placeholder": "Start typing to search or add tags",
    "minimumInputLength": 1,
    "allowClear": True,
    "width": "100%",
}

# Jazzmin removed. Using custom admin shell built on vanilla Django admin.
# Admin bar removed. No separate frontend admin bar.

ENABLE_ADMIN_CONTROL = os.getenv("ENABLE_ADMIN_CONTROL", "true").lower() == "true"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "seo-apply-due-autofixes-hourly": {
        "task": "seo.tasks.seo_apply_due_autofixes",
        "schedule": 60 * 60,
    },
    "seo-scheduled-full-scan-daily": {
        "task": "seo.tasks.seo_schedule_full_scan",
        "schedule": 60 * 60 * 24,
    },
}
