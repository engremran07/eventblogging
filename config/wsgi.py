"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APPS_DIR = str(BASE_DIR / "apps")
if APPS_DIR not in sys.path:
    sys.path.insert(0, APPS_DIR)


def get_application():
    from django.core.wsgi import get_wsgi_application

    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        os.getenv("DJANGO_SETTINGS_MODULE", "config.settings.production"),
    )
    return get_wsgi_application()


application = get_application()
