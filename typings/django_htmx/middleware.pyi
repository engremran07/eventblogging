"""Type stubs for django-htmx middleware."""

from django.http import HttpRequest as _HttpRequest


class HtmxDetails:
    """Information about the current HTMX request."""

    boosted: bool
    current_url: str | None
    history_restore_request: bool
    prompt: str | None
    target: str | None
    trigger: str | None
    trigger_name: str | None

    def __bool__(self) -> bool: ...


class HtmxMiddleware:
    def __init__(self, get_response: object) -> None: ...
    def __call__(self, request: _HttpRequest) -> object: ...
