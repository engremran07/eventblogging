"""
Settings router — imports the correct settings module based on DJANGO_ENV.
Default: development. Set DJANGO_ENV=production in production.
"""
import os

_env = os.environ.get("DJANGO_ENV", "development").lower()

if _env == "production":
    from .settings.production import *  # noqa: F403
elif _env == "testing":
    from .settings.testing import *  # noqa: F403
else:
    from .settings.development import *  # noqa: F403
