"""Type stubs for django-htmx http utilities."""

from typing import Any

from django.http import HttpResponse, HttpResponseRedirectBase


def trigger_client_event(
    response: HttpResponse,
    name: str,
    params: dict[str, Any] | None = None,
    *,
    after: str = "receive",
) -> HttpResponse: ...


class HttpResponseClientRedirect(HttpResponseRedirectBase):
    status_code: int
    def __init__(self, redirect_to: str, *args: Any, **kwargs: Any) -> None: ...


class HttpResponseClientRefresh(HttpResponse):
    def __init__(self, **kwargs: Any) -> None: ...


class HttpResponseStopPolling(HttpResponse):
    status_code: int
    def __init__(self, **kwargs: Any) -> None: ...


class HttpResponseLocation(HttpResponse):
    def __init__(
        self,
        redirect_to: str,
        *,
        target: str | None = None,
        select: str | None = None,
        swap: str | None = None,
        values: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        source: str | None = None,
        **kwargs: Any,
    ) -> None: ...


def push_url(response: HttpResponse, url: str | bool) -> HttpResponse: ...
def reswap(response: HttpResponse, method: str) -> HttpResponse: ...
def retarget(response: HttpResponse, target: str) -> HttpResponse: ...
