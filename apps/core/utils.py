"""
Utility functions for core app.
Includes rate limiting, caching, and common helpers.
"""

import hashlib
from datetime import timedelta
from functools import wraps
from typing import Any, Callable

from django.core.cache import cache
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.utils import timezone


def rate_limit(
    max_calls: int = 100,
    time_window_seconds: int = 3600
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Simple rate limiting decorator for views.
    Limits requests per IP address.

    Args:
        max_calls: Maximum number of calls allowed in the time window
        time_window_seconds: Time window in seconds (default 1 hour)

    Example:
        @rate_limit(max_calls=100, time_window_seconds=3600)
        def api_view(request):
            return JsonResponse({...})
    """
    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            # Get client IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', 'unknown')

            # Create cache key
            cache_key = f'rate_limit:{view_func.__name__}:{ip}'

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
            cache_key = f'view:{view_func.__name__}:{request.GET.urlencode()}'

            # Check cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Call view
            response = view_func(request, *args, **kwargs)

            # Cache if successful
            if response.status_code == 200:
                cache.set(cache_key, response, cache_ttl)

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
