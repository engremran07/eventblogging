"""
Pages app database query selectors.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Page, PageRevision


def get_page_by_slug(slug: str, user: User | None = None) -> Page:
    page = get_object_or_404(
        Page.objects.select_related("author"),
        slug=slug,
    )

    if user and user.is_authenticated and (user == page.author or user.is_staff):
        return page

    if (
        page.status == Page.Status.PUBLISHED
        and page.published_at is not None
        and page.published_at <= timezone.now()
    ):
        return page

    raise Http404("Page not available")


def get_published_pages() -> QuerySet[Page]:
    return (
        Page.objects.filter(
            status=Page.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )
        .select_related("author")
        .order_by("-published_at")
    )


def get_navigation_pages(limit: int = 4) -> QuerySet[Page]:
    return (
        Page.objects.filter(
            show_in_navigation=True,
            status=Page.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )
        .select_related("author")
        .order_by("nav_order")[:limit]
    )


def get_featured_pages() -> QuerySet[Page]:
    return (
        Page.objects.filter(
            is_featured=True,
            status=Page.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )
        .select_related("author")
        .order_by("-published_at")
    )


def get_user_pages(user: User) -> QuerySet[Page]:
    return (
        Page.objects.filter(author=user)
        .select_related("author")
        .order_by("-updated_at")
    )


def get_admin_pages(search: str = "", status: str = "") -> QuerySet[Page]:
    pages = Page.objects.select_related("author")

    valid_statuses = {choice[0] for choice in Page.Status.choices}
    if status in valid_statuses:
        pages = pages.filter(status=status)

    if search:
        pages = pages.filter(
            Q(title__icontains=search)
            | Q(slug__icontains=search)
            | Q(body_markdown__icontains=search)
        )

    return pages.order_by("-updated_at")


def search_pages(query: str) -> QuerySet[Page]:
    clean_query = (query or "").strip()
    if not clean_query:
        return Page.objects.none()

    return get_published_pages().filter(
        Q(title__icontains=clean_query)
        | Q(summary__icontains=clean_query)
        | Q(body_markdown__icontains=clean_query)
    )


def get_policy_pages() -> QuerySet[Page]:
    policy_slugs = ["privacy-policy", "terms-of-service", "cookie-policy", "disclaimer"]
    return get_published_pages().filter(slug__in=policy_slugs)


def get_page_revisions(page: Page) -> QuerySet[PageRevision]:
    return (
        PageRevision.objects.filter(page=page)
        .select_related("editor")
        .order_by("-created_at")
    )


def get_page_revision(page: Page, revision_id: int) -> PageRevision:
    return get_object_or_404(
        PageRevision.objects.select_related("editor"),
        page=page,
        id=revision_id,
    )
