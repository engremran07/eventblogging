"""Backward-compat shim — canonical location is core.services."""
from core.services import emit_platform_webhook

__all__ = ["emit_platform_webhook"]
