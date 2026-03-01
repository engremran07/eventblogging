"""
Utility functions for core app.
Includes rate limiting, caching, and common helpers.
"""

import logging
from functools import wraps
from typing import Any, Callable

from django.core.cache import cache
from django.http import JsonResponse, HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


def rate_limit(
    max_calls: int = 100,
    time_window_seconds: int = 3600
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Simple rate limiting decorator for views.
    Limits requests per IP address.

    The cache key includes the view module + qualified name so that two views
    in different modules that happen to share the same function name don't
    incorrectly share a rate-limit bucket.

    Args:
        max_calls: Maximum number of calls allowed in the time window
        time_window_seconds: Time window in seconds (default 1 hour)

    Example:
        @rate_limit(max_calls=100, time_window_seconds=3600)
        def api_view(request):
            return JsonResponse({...})
    """
    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        # Build a stable, module-qualified key prefix once at decoration time.
        qualified_name = f"{view_func.__module__}.{view_func.__qualname__}"

        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            # Get client IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', 'unknown')

            # Create cache key — uses module-qualified name to prevent bucket clashes
            cache_key = f'rate_limit:{qualified_name}:{ip}'

            # Check current count
            current_count = cache.get(cache_key, 0)

            if current_count >= max_calls:
                return JsonResponse(
                    {
                        'detail': f'Rate limit exceeded. Maximum {max_calls} requests per {time_window_seconds} seconds.',
                        'retry_after': time_window_seconds,
                    },
                    status=429,  # Too Many Requests
                )

            # Increment counter and set expiry
            cache.set(cache_key, current_count + 1, time_window_seconds)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def cache_view_result(cache_ttl: int = 300) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Cache view results for a given time-to-live (TTL).
    Useful for expensive queries that don't need real-time updates.

    Only plain ``HttpResponse`` with a 200 status is cached.  Streaming
    responses and non-200 responses are **never** cached.

    The cache stores ``(content_bytes, content_type)`` — not the full
    ``HttpResponse`` object — so it is safe to use with Redis/Memcached
    backends that use ``pickle`` serialisation.

    Args:
        cache_ttl: Cache time-to-live in seconds (default 5 minutes)

    Example:
        @cache_view_result(cache_ttl=600)
        def expensive_view(request):
            return JsonResponse({...})
    """
    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            # Create cache key based on view and query params
            cache_key = f'view:{view_func.__module__}.{view_func.__qualname__}:{request.GET.urlencode()}'

            # Check cache
            cached = cache.get(cache_key)
            if cached is not None:
                content_bytes: bytes
                content_type: str
                content_bytes, content_type = cached
                return HttpResponse(content_bytes, content_type=content_type)

            # Call view
            response = view_func(request, *args, **kwargs)

            # Only cache plain 200 responses — streaming responses have no .content
            if response.status_code == 200 and hasattr(response, 'content'):
                try:
                    cache.set(cache_key, (response.content, response.get('Content-Type', 'text/html')), cache_ttl)
                except Exception:
                    # Serialisation failure should not break the response.
                    logger.warning(
                        "cache_view_result: failed to store response for key %r", cache_key, exc_info=True
                    )

            return response

        return wrapper
    return decorator


def get_client_ip(request: HttpRequest) -> str:
    """
    Extract client IP address from request.
    Respects X-Forwarded-For header for proxied requests.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def cache_feature_control_settings(timeout: int = 3600) -> Any:
    """
    Cache feature control settings to avoid DB hits on every request.

    Args:
        timeout: Cache timeout in seconds (default 1 hour)

    Returns:
        Cached FeatureControlSettings instance
    """
    from .models import FeatureControlSettings

    cache_key = 'feature_control_settings'
    settings = cache.get(cache_key)

    if settings is None:
        settings = FeatureControlSettings.get_solo()
        cache.set(cache_key, settings, timeout)

    return settings


def invalidate_feature_control_cache() -> None:
    """Invalidate feature control settings cache."""
    cache.delete('feature_control_settings')
