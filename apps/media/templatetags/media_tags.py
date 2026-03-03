"""Custom template tags and filters for the media app."""

from __future__ import annotations

from django import template

register = template.Library()


@register.filter(name="add_int")
def add_int(value: int | str, arg: int | str) -> int:
    """Add two values as integers. Used for incrementing tree depth."""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return 0
