"""
Tags app database query selectors.
"""

from __future__ import annotations

from django.db.models import Count, QuerySet
from tagulous.models import TagModel

# ============================================================================
# TAG SELECTORS
# ============================================================================

def get_all_tags() -> QuerySet[TagModel]:
    """Get all tags ordered by frequency."""
    return TagModel.objects.annotate(
        usage_count=Count('tagged_items')
    ).order_by('-usage_count')


def get_all_tags_with_counts() -> QuerySet[TagModel]:
    """Get all tags with post counts, ordered by count desc.  Canonical alias."""
    return get_all_tags()


def get_popular_tags(limit: int = 20) -> QuerySet[TagModel]:
    """Get most popular tags."""
    return get_all_tags()[:limit]


def get_tag_by_name(name: str) -> TagModel | None:
    """Get a tag by name."""
    try:
        return TagModel.objects.get(name__iexact=name)
    except TagModel.DoesNotExist:
        return None


def search_tags(query: str) -> QuerySet[TagModel]:
    """Search tags by name."""
    clean_query = (query or "").strip()
    if not clean_query:
        return TagModel.objects.none()
    
    return TagModel.objects.filter(
        name__icontains=clean_query
    ).annotate(
        usage_count=Count('tagged_items')
    ).order_by('-usage_count')


def get_tags_autocomplete(query: str, limit: int = 30) -> QuerySet[TagModel]:
    """Get tags for autocomplete dropdown."""
    if not query or not query.strip():
        return TagModel.objects.all()[:limit]
    
    return TagModel.objects.filter(
        name__icontains=query.strip()
    )[:limit]


# ============================================================================
# CATEGORY SELECTORS (Hierarchical Tags)
# ============================================================================

def get_all_categories() -> QuerySet[TagModel]:
    """Get all categories with hierarchy support."""
    return TagModel.objects.all().order_by('name')


def get_root_categories() -> QuerySet[TagModel]:
    """Get top-level categories (no parent)."""
    return TagModel.objects.filter(name__regex=r'^[^/]+$').order_by('name')


def get_subcategories(parent_name: str) -> QuerySet[TagModel]:
    """Get subcategories for a parent category."""
    return TagModel.objects.filter(
        name__startswith=f'{parent_name}/'
    ).order_by('name')


def get_category_by_path(path: str) -> TagModel | None:
    """Get a category by its full path (e.g., 'technology/python')."""
    try:
        return TagModel.objects.get(name__iexact=path)
    except TagModel.DoesNotExist:
        return None


# ============================================================================
# TOPIC SELECTORS
# ============================================================================

def get_all_topics() -> QuerySet[TagModel]:
    """Get all topics."""
    return TagModel.objects.all().order_by('name')


def get_topic_by_name(name: str) -> TagModel | None:
    """Get a topic by name."""
    try:
        return TagModel.objects.get(name__iexact=name)
    except TagModel.DoesNotExist:
        return None
