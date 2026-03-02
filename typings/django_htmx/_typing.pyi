"""Augment Django's HttpRequest with django-htmx attributes."""

from django_htmx.middleware import HtmxDetails


class HtmxHttpRequest:
    """Mixin that adds the `htmx` attribute set by HtmxMiddleware."""

    htmx: HtmxDetails
