"""
Centralized session helpers used across the project.

This module is the single source of truth for:
- session key lifecycle
- session fingerprinting for storage/analytics
- namespaced session markers
"""

from __future__ import annotations

from django.conf import settings
from django.utils.crypto import salted_hmac


class SessionService:
    """Unified session API for request-level workflows."""

    FINGERPRINT_SALT = "core.session.fingerprint"

    @classmethod
    def ensure_session_key(cls, request) -> str:
        """
        Ensure the current request has a persisted session key and return it.
        """
        if request.session.session_key:
            return request.session.session_key

        request.session.save()
        return request.session.session_key or ""

    @classmethod
    def fingerprint(cls, request) -> str:
        """
        Return a non-reversible session fingerprint for storage/logging.
        """
        raw_key = cls.ensure_session_key(request)
        if not raw_key:
            return ""
        return salted_hmac(cls.FINGERPRINT_SALT, raw_key).hexdigest()

    @classmethod
    def marker_key(cls, namespace: str, identifier: str | int) -> str:
        """
        Build a namespaced marker key under a single configurable prefix.
        """
        prefix = str(getattr(settings, "SESSION_MARKER_PREFIX", "app")).strip() or "app"
        normalized_namespace = str(namespace).strip().replace(" ", "_").lower() or "global"
        normalized_identifier = str(identifier).strip().replace(" ", "_").lower() or "default"
        return f"{prefix}:{normalized_namespace}:{normalized_identifier}"

    @classmethod
    def is_marked(cls, request, namespace: str, identifier: str | int) -> bool:
        return bool(request.session.get(cls.marker_key(namespace, identifier), False))

    @classmethod
    def mark(cls, request, namespace: str, identifier: str | int, value: bool = True) -> None:
        request.session[cls.marker_key(namespace, identifier)] = bool(value)
