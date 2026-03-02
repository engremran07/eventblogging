"""Augment Django's HttpRequest with django-htmx `htmx` attribute.

django-htmx 1.x sets ``request.htmx`` at runtime via middleware.
Django-stubs doesn't know about this attribute, so we extend HttpRequest here.

References:
    https://django-htmx.readthedocs.io/en/latest/middleware.html
"""

from __future__ import annotations

from django_htmx.middleware import HtmxDetails
from django.http import HttpRequest


class __HtmxRequest(HttpRequest):
    htmx: HtmxDetails
