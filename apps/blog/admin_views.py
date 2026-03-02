"""
Custom admin content workspace views.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Avg, Count, Max, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django_htmx.http import HttpResponseClientRedirect
from tagulous.models import BaseTagModel, BaseTagTreeModel

from comments.models import Comment
from core.constants import ADMIN_PAGINATION_SIZE
from core.models import (
    APPEARANCE_PRESET_CHOICES,
    FeatureControlSettings,
    IntegrationSettings,
    SeoSettings,
    SiteAppearanceSettings,
    SiteIdentitySettings,
)
from pages.models import Page
from pages.policies import POLICY_SLUGS
from seo.services import audit_content_batch

from .context_processors import invalidate_admin_nav_badges_cache
from .models import Post
from .services import apply_auto_taxonomy_to_post
from .taxonomy_rules import get_category_max_depth, split_category_string, validate_category_depth

ADMIN_WORKSPACE_PAGE_SIZE = ADMIN_PAGINATION_SIZE
POSTS_PAGE_SIZE = ADMIN_WORKSPACE_PAGE_SIZE
COMMENTS_PAGE_SIZE = ADMIN_WORKSPACE_PAGE_SIZE
PAGES_PAGE_SIZE = ADMIN_WORKSPACE_PAGE_SIZE
TAXONOMY_PAGE_SIZE = ADMIN_WORKSPACE_PAGE_SIZE
USERS_PAGE_SIZE = ADMIN_WORKSPACE_PAGE_SIZE
GROUPS_PAGE_SIZE = ADMIN_WORKSPACE_PAGE_SIZE
logger = logging.getLogger(__name__)
VALID_POST_SORTS = {
    "title",
    "-title",
    "published_at",
    "-published_at",
    "created_at",
    "-created_at",
    "word_count",
    "-word_count",
    "seo_audit_score",
    "-seo_audit_score",
    "views_count",
    "-views_count",
}
POSTS_BULK_ACTIONS = {"publish", "review", "draft", "archive", "delete"}
VALID_COMMENT_SORTS = {"-created_at", "created_at", "-updated_at", "updated_at"}
VALID_PAGE_SORTS = {"-updated_at", "updated_at", "-published_at", "published_at", "title", "-title"}
VALID_FLAT_TAG_SORTS = {"-count", "count", "name", "-name"}
VALID_CATEGORY_SORTS = {"path", "-count", "count", "level", "-level", "name", "-name"}
VALID_USER_SORTS = {"-date_joined", "date_joined", "username", "-username", "-last_login", "last_login"}
VALID_GROUP_SORTS = {"name", "-name", "-user_count", "user_count", "-permission_count", "permission_count"}


def _query_without_page(request: HttpRequest) -> str:
    query = request.GET.copy()
    query.pop("page", None)
    return query.urlencode()


def _clean_post_ids(raw_ids: list[str]) -> list[int]:
    cleaned: list[int] = []
    for raw in raw_ids:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            cleaned.append(value)
    return cleaned


def _resolve_next_url(request: HttpRequest, fallback_url_name: str) -> str:
    candidate = (request.POST.get("next_url") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        if candidate.startswith("/admin/"):
            return candidate
    return reverse(fallback_url_name)


def _redirect_next(request: HttpRequest, fallback_url_name: str) -> HttpResponse:
    next_url = _resolve_next_url(request, fallback_url_name)
    if request.headers.get("HX-Request"):
        return HttpResponseClientRedirect(next_url)
    return redirect(next_url)


def _get_post_categories() -> list[BaseTagModel]:
    try:
        return list(Post.categories.tag_model.objects.order_by("name"))
    except Exception:
        logger.warning("Could not load post categories for admin filter", exc_info=True)
        return []


def _build_posts_queryset(request: HttpRequest):
    posts = Post.objects.select_related("author").prefetch_related("categories", "tags")
    valid_statuses = {choice[0] for choice in Post.Status.choices}

    status_filter = request.GET.get("status", "").strip()
    category_filter = request.GET.get("category", "").strip()
    search_query = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort", "-published_at").strip() or "-published_at"

    if status_filter in valid_statuses:
        posts = posts.filter(status=status_filter)
    else:
        status_filter = ""

    if category_filter:
        posts = posts.filter(categories__name__icontains=category_filter)

    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query)
            | Q(slug__icontains=search_query)
            | Q(tags__name__icontains=search_query)
        ).distinct()

    if sort_by not in VALID_POST_SORTS:
        sort_by = "-published_at"

    posts = posts.order_by(sort_by)
    return posts, status_filter, category_filter, search_query, sort_by


def _execute_posts_bulk_action(*, action: str, selected_ids: list[int]) -> int:
    queryset = Post.objects.filter(pk__in=selected_ids)
    count = queryset.count()
    if count == 0:
        return 0

    now = timezone.now()
    if action == "delete":
        queryset.delete()
        return count

    if action == "publish":
        queryset.update(status=Post.Status.PUBLISHED, updated_at=now)
        queryset.filter(published_at__isnull=True).update(published_at=now)
        return count

    if action == "review":
        queryset.update(status=Post.Status.REVIEW, updated_at=now)
        return count

    if action == "archive":
        queryset.update(status=Post.Status.ARCHIVED, updated_at=now)
        return count

    if action == "draft":
        queryset.update(status=Post.Status.DRAFT, updated_at=now)
        return count

    return 0


def _bulk_action_message(action: str, count: int) -> str:
    labels = {
        "publish": f"{count} posts published.",
        "review": f"{count} posts moved to review.",
        "draft": f"{count} posts moved to draft.",
        "archive": f"{count} posts archived.",
        "delete": f"{count} posts deleted.",
    }
    return labels.get(action, f"{count} posts updated.")


def _handle_posts_bulk_action(request: HttpRequest, *, forced_action: str | None = None):
    action = (forced_action or request.POST.get("bulk_action", "")).strip().lower()
    selected_ids = _clean_post_ids(request.POST.getlist("selected_posts"))

    if action not in POSTS_BULK_ACTIONS:
        messages.error(request, "Invalid bulk action.")
        if request.headers.get("HX-Request"):
            return HttpResponse("Invalid bulk action.", status=400)
        return redirect("admin_posts_list")

    if not selected_ids:
        messages.warning(request, "Select at least one post.")
        if request.headers.get("HX-Request"):
            return HttpResponse("No posts selected.", status=400)
        return redirect("admin_posts_list")

    count = _execute_posts_bulk_action(action=action, selected_ids=selected_ids)
    if count == 0:
        messages.warning(request, "No matching posts found.")
        if request.headers.get("HX-Request"):
            return HttpResponse("No matching posts found.", status=404)
        return redirect("admin_posts_list")

    if action != "delete":
        try:
            audit_content_batch("post", selected_ids, trigger="save", run_autopilot=True)
        except Exception:
            logger.exception("SEO refresh failed after admin post bulk action '%s'.", action)

    messages.success(request, _bulk_action_message(action, count))
    if request.headers.get("HX-Request"):
        return HttpResponse(status=204)
    return redirect("admin_posts_list")


def _build_comments_queryset(request: HttpRequest):
    comments = Comment.objects.select_related("post", "author")
    status_filter = request.GET.get("status", "").strip().lower()
    search_query = request.GET.get("search", "").strip()
    post_filter = request.GET.get("post", "").strip()
    sort_by = request.GET.get("sort", "-created_at").strip() or "-created_at"

    if status_filter == "pending":
        comments = comments.filter(is_approved=False)
    elif status_filter == "approved":
        comments = comments.filter(is_approved=True)
    else:
        status_filter = ""

    if search_query:
        comments = comments.filter(
            Q(author__username__icontains=search_query)
            | Q(post__title__icontains=search_query)
            | Q(body__icontains=search_query)
        )

    if post_filter:
        try:
            comments = comments.filter(post_id=int(post_filter))
        except (TypeError, ValueError):
            post_filter = ""

    if sort_by not in VALID_COMMENT_SORTS:
        sort_by = "-created_at"

    comments = comments.order_by(sort_by)
    return comments, status_filter, search_query, post_filter, sort_by


def _editor_context(post: Post, *, posted_values: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if posted_values is None:
        if post.pk:
            primary_topic = post.primary_topic.name if post.primary_topic else ""
            tags = ", ".join(tag.name for tag in post.tags.all())
            categories = ", ".join(category.name for category in post.categories.all())
        else:
            primary_topic = ""
            tags = ""
            categories = ""
    else:
        primary_topic = posted_values.get("primary_topic", "").strip()
        tags = posted_values.get("tags", "").strip()
        categories = posted_values.get("categories", "").strip()
    if posted_values is None:
        publish_at_value = (
            timezone.localtime(post.published_at).strftime("%Y-%m-%dT%H:%M")
            if post.published_at
            else ""
        )
    else:
        publish_at_value = posted_values.get("publish_at", "").strip()

    return {
        "post": post,
        "status_choices": Post.Status.choices,
        "primary_topic_value": primary_topic,
        "tags_value": tags,
        "categories_value": categories,
        "publish_at_value": publish_at_value,
        "category_max_depth": get_category_max_depth(),
    }


def _parse_publish_at(raw_value: str):
    raw = (raw_value or "").strip()
    if not raw:
        return None, ""
    parsed = parse_datetime(raw)
    if parsed is None:
        return None, "Invalid publish schedule. Use a valid date and time."
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed, ""


@staff_member_required
@require_http_methods(["GET"])
def admin_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Legacy dashboard endpoint for custom admin namespace.
    """
    published_posts = Post.objects.filter(status=Post.Status.PUBLISHED).count()
    draft_posts = Post.objects.filter(status=Post.Status.DRAFT).count()
    pending_comments = Comment.objects.filter(is_approved=False).count()
    approved_comments = Comment.objects.filter(is_approved=True).count()
    avg_seo_score = (
        Post.objects.filter(status=Post.Status.PUBLISHED).aggregate(
            avg_score=Avg("seo_audit_score")
        )["avg_score"]
        or 0
    )

    recent_posts = (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .select_related("author")
        .order_by("-published_at")[:10]
    )
    recent_comments = (
        Comment.objects.filter(is_approved=False)
        .select_related("post", "author")
        .order_by("-created_at")[:5]
    )
    seo_pending_count = 0
    try:
        from seo.models import SeoSuggestion

        seo_pending_count = SeoSuggestion.objects.filter(
            status=SeoSuggestion.Status.PENDING
        ).count()
    except Exception:
        seo_pending_count = 0

    context = {
        "total_posts": Post.objects.count(),
        "published_posts": published_posts,
        "draft_posts": draft_posts,
        "pending_comments": pending_comments,
        "approved_comments": approved_comments,
        "avg_seo_score": round(avg_seo_score, 1),
        "recent_posts": recent_posts,
        "recent_comments": recent_comments,
        "pending_comments_list": recent_comments,
        "seo_pending_count": seo_pending_count,
    }
    return render(request, "admin/dashboard.html", context)


@staff_member_required
@require_http_methods(["GET"])
def admin_posts_list(request: HttpRequest) -> HttpResponse:
    """
    Posts management list page with filters and HTMX partial rendering.
    """
    posts, status_filter, category_filter, search_query, sort_by = _build_posts_queryset(
        request
    )
    page_obj = Paginator(posts, POSTS_PAGE_SIZE).get_page(request.GET.get("page", 1))

    context = {
        "page_obj": page_obj,
        "posts": page_obj.object_list,
        "status_filter": status_filter,
        "category_filter": category_filter,
        "search_query": search_query,
        "sort_by": sort_by,
        "status_choices": Post.Status.choices,
        "categories": _get_post_categories(),
        "is_paginated": page_obj.has_other_pages(),
        "total_posts": Post.objects.count(),
        "published_posts": Post.objects.filter(status=Post.Status.PUBLISHED).count(),
        "draft_posts": Post.objects.filter(status=Post.Status.DRAFT).count(),
        "review_posts": Post.objects.filter(status=Post.Status.REVIEW).count(),
        "archived_posts": Post.objects.filter(status=Post.Status.ARCHIVED).count(),
        "page_query": _query_without_page(request),
    }

    if request.headers.get("HX-Request"):
        return render(request, "admin/posts/table.html", context)
    return render(request, "admin/posts/list.html", context)


@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_post_editor(request: HttpRequest, post_id: int | None = None) -> HttpResponse:
    """
    Post editor view.
    """
    if post_id:
        post = get_object_or_404(Post, pk=post_id)
    else:
        post = Post(author=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "").strip().lower()
        if action == "delete":
            if not post.pk:
                messages.error(request, "Cannot delete an unsaved post.")
                return render(
                    request,
                    "admin/posts/editor.html",
                    _editor_context(post, posted_values=request.POST),
                    status=400,
                )
            post.delete()
            if request.headers.get("HX-Request"):
                return HttpResponse(status=204)
            messages.success(request, "Post deleted.")
            return redirect("admin_posts_list")

        valid_statuses = {choice[0] for choice in Post.Status.choices}
        action_to_status = {
            "draft": Post.Status.DRAFT,
            "review": Post.Status.REVIEW,
            "published": Post.Status.PUBLISHED,
        }
        next_status = action_to_status.get(action) or request.POST.get(
            "status", Post.Status.DRAFT
        ).strip()
        if next_status not in valid_statuses:
            next_status = Post.Status.DRAFT

        post.title = request.POST.get("title", "").strip()
        post.slug = request.POST.get("slug", "").strip()
        post.excerpt = request.POST.get("excerpt", "").strip()
        post.canonical_url = request.POST.get("canonical_url", "").strip()
        post.body_markdown = (
            request.POST.get("body_markdown", "").strip()
            or request.POST.get("body", "").strip()
        )
        post.meta_title = request.POST.get("meta_title", "").strip()
        post.meta_description = request.POST.get("meta_description", "").strip()
        post.status = next_status
        post.is_featured = bool(request.POST.get("is_featured"))
        post.is_editors_pick = bool(request.POST.get("is_editors_pick"))
        post.allow_comments = bool(request.POST.get("allow_comments"))
        post.allow_reactions = bool(request.POST.get("allow_reactions"))
        publish_at, publish_at_error = _parse_publish_at(request.POST.get("publish_at", ""))

        if not post.title:
            messages.error(request, "Title is required.")
            if request.headers.get("HX-Request"):
                return HttpResponse("Title is required.", status=400)
            return render(
                request,
                "admin/posts/editor.html",
                _editor_context(post, posted_values=request.POST),
                status=400,
            )

        if publish_at_error:
            messages.error(request, publish_at_error)
            if request.headers.get("HX-Request"):
                return HttpResponse(publish_at_error, status=400)
            return render(
                request,
                "admin/posts/editor.html",
                _editor_context(post, posted_values=request.POST),
                status=400,
            )

        if post.slug and Post.objects.exclude(pk=post.pk).filter(slug=post.slug).exists():
            message = "Slug is already in use. Choose a unique slug."
            messages.error(request, message)
            if request.headers.get("HX-Request"):
                return HttpResponse(message, status=400)
            return render(
                request,
                "admin/posts/editor.html",
                _editor_context(post, posted_values=request.POST),
                status=400,
            )

        if next_status == Post.Status.PUBLISHED:
            post.published_at = publish_at or timezone.now()
        elif next_status in {Post.Status.DRAFT, Post.Status.REVIEW}:
            post.published_at = None

        try:
            post.save()  # type: ignore[misc]  # Tagulous patches Post.save() at runtime
        except IntegrityError:
            message = "Unable to save post due to conflicting data. Check slug uniqueness."
            messages.error(request, message)
            if request.headers.get("HX-Request"):
                return HttpResponse(message, status=400)
            return render(
                request,
                "admin/posts/editor.html",
                _editor_context(post, posted_values=request.POST),
                status=400,
            )
        post.primary_topic = request.POST.get("primary_topic", "").strip()
        categories_input = request.POST.get("categories", "").strip()
        try:
            validate_category_depth(split_category_string(categories_input))
        except ValidationError as exc:
            error_message = exc.messages[0] if exc.messages else "Invalid categories."
            messages.error(request, error_message)
            if request.headers.get("HX-Request"):
                return HttpResponse(error_message, status=400)
            return render(
                request,
                "admin/posts/editor.html",
                _editor_context(post, posted_values=request.POST),
                status=400,
            )
        try:
            post.tags.set_tag_string(request.POST.get("tags", "").strip())
            post.categories.set_tag_string(categories_input)
            post.save(update_fields=["primary_topic", "updated_at"])  # type: ignore[misc]  # Tagulous patches Post.save()
            apply_auto_taxonomy_to_post(post)
        except Exception:
            logger.exception("Post taxonomy sync failed for post_id=%s.", post.pk)
            messages.warning(
                request,
                "Post saved, but taxonomy sync failed. Verify tag/category format and retry.",
            )
            if request.headers.get("HX-Request"):
                return HttpResponse(status=204)
            return redirect("admin_posts_list")

        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)

        messages.success(request, "Post saved successfully.")
        return redirect("admin_posts_list")

    return render(request, "admin/posts/editor.html", _editor_context(post))


@staff_member_required
@require_http_methods(["POST"])
def admin_posts_bulk_action(request: HttpRequest) -> HttpResponse:
    """
    Bulk action endpoint for posts.
    """
    return _handle_posts_bulk_action(request)


@staff_member_required
@require_http_methods(["POST"])
def admin_bulk_delete_posts(request: HttpRequest) -> HttpResponse:
    """
    Compatibility endpoint for legacy delete-only bulk action.
    """
    return _handle_posts_bulk_action(request, forced_action="delete")


@staff_member_required
@require_http_methods(["GET"])
def admin_comments_list(request: HttpRequest) -> HttpResponse:
    """
    Comments moderation list with filtering and HTMX partial rendering.
    """
    comments, status_filter, search_query, post_filter, sort_by = _build_comments_queryset(
        request
    )
    page_obj = Paginator(comments, COMMENTS_PAGE_SIZE).get_page(request.GET.get("page", 1))
    post_choices = Post.objects.only("id", "title").order_by("-updated_at")[:200]

    context = {
        "page_obj": page_obj,
        "comments": page_obj.object_list,
        "status_filter": status_filter,
        "search_query": search_query,
        "post_filter": post_filter,
        "sort_by": sort_by,
        "post_choices": post_choices,
        "pending_count": Comment.objects.filter(is_approved=False).count(),
        "approved_count": Comment.objects.filter(is_approved=True).count(),
        "total_comments": Comment.objects.count(),
        "is_paginated": page_obj.has_other_pages(),
        "page_query": _query_without_page(request),
    }

    if request.headers.get("HX-Request"):
        return render(request, "admin/comments/table.html", context)
    return render(request, "admin/comments/list.html", context)


@staff_member_required
@require_http_methods(["POST"])
def admin_comments_bulk_action(request: HttpRequest) -> HttpResponse:
    action = (request.POST.get("bulk_action") or "").strip().lower()
    selected_ids = _clean_post_ids(request.POST.getlist("selected_comments"))

    if not selected_ids:
        messages.warning(request, "Select at least one comment.")
        return _redirect_next(request, "admin_comments_list")

    queryset = Comment.objects.filter(id__in=selected_ids)
    if not queryset.exists():
        messages.warning(request, "No matching comments found.")
        return _redirect_next(request, "admin_comments_list")

    if action == "approve":
        count = queryset.update(is_approved=True)
        messages.success(request, f"{count} comments approved.")
    elif action == "unapprove":
        count = queryset.update(is_approved=False)
        messages.success(request, f"{count} comments unapproved.")
    elif action == "delete":
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"{count} comments deleted.")
    else:
        messages.error(request, "Invalid comment bulk action.")
        return _redirect_next(request, "admin_comments_list")

    invalidate_admin_nav_badges_cache()
    return _redirect_next(request, "admin_comments_list")


@staff_member_required
@require_http_methods(["PATCH", "POST"])
def admin_comment_approve(request: HttpRequest, comment_id: int) -> HttpResponse:
    """
    Approve a comment.
    """
    comment = get_object_or_404(Comment, pk=comment_id)
    if not comment.is_approved:
        comment.is_approved = True
        comment.save(update_fields=["is_approved"])
        messages.success(request, "Comment approved.")
    else:
        messages.info(request, "Comment already approved.")

    invalidate_admin_nav_badges_cache()
    pending_comments = Comment.objects.filter(is_approved=False).count()

    if request.headers.get("HX-Request"):
        return render(
            request,
            "admin/comments/comment_item_response.html",
            {
                "comment": comment,
                "pending_comments": pending_comments,
            },
        )
    return redirect("admin_comments_list")


@staff_member_required
@require_http_methods(["DELETE", "POST"])
def admin_comment_delete(request: HttpRequest, comment_id: int) -> HttpResponse:
    """
    Delete a comment.
    """
    comment = get_object_or_404(Comment, pk=comment_id)
    comment.delete()
    invalidate_admin_nav_badges_cache()

    if request.headers.get("HX-Request"):
        return HttpResponse(status=204)
    return redirect("admin_comments_list")


def _yes_no_to_bool(value: str):
    clean = (value or "").strip().lower()
    if clean == "yes":
        return True
    if clean == "no":
        return False
    return None


def _build_pages_workspace_queryset(request: HttpRequest):
    pages = Page.objects.select_related("author")
    status_filter = request.GET.get("status", "").strip()
    template_filter = request.GET.get("template", "").strip()
    nav_filter = request.GET.get("nav", "").strip()
    search_query = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort", "-updated_at").strip() or "-updated_at"

    valid_statuses = {choice[0] for choice in Page.Status.choices}
    valid_templates = {choice[0] for choice in Page.TemplateKey.choices}

    if status_filter in valid_statuses:
        pages = pages.filter(status=status_filter)
    else:
        status_filter = ""

    if template_filter in valid_templates:
        pages = pages.filter(template_key=template_filter)
    else:
        template_filter = ""

    nav_value = _yes_no_to_bool(nav_filter)
    if nav_value is not None:
        pages = pages.filter(show_in_navigation=nav_value)
    else:
        nav_filter = ""

    if search_query:
        pages = pages.filter(
            Q(title__icontains=search_query)
            | Q(slug__icontains=search_query)
            | Q(summary__icontains=search_query)
            | Q(author__username__icontains=search_query)
        )

    if sort_by not in VALID_PAGE_SORTS:
        sort_by = "-updated_at"

    pages = pages.order_by(sort_by)
    return pages, status_filter, template_filter, nav_filter, search_query, sort_by


def _build_flat_taxonomy_queryset(request: HttpRequest, *, model: type[BaseTagModel], valid_sorts: set[str]) -> tuple[Any, str, str, str]:
    rows = model.objects.all()
    protected_filter = request.GET.get("protected", "").strip()
    search_query = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort", "-count").strip() or "-count"

    protected_value = _yes_no_to_bool(protected_filter)
    if protected_value is not None:
        rows = rows.filter(protected=protected_value)
    else:
        protected_filter = ""

    if search_query:
        rows = rows.filter(Q(name__icontains=search_query) | Q(slug__icontains=search_query))

    if sort_by not in valid_sorts:
        sort_by = "-count"

    rows = rows.order_by(sort_by)
    return rows, protected_filter, search_query, sort_by


def _build_category_taxonomy_queryset(request: HttpRequest, *, model: type[BaseTagModel]) -> tuple[Any, str, str, str, str]:
    rows = model.objects.select_related("parent")
    protected_filter = request.GET.get("protected", "").strip()
    level_filter = request.GET.get("level", "").strip()
    search_query = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort", "path").strip() or "path"

    protected_value = _yes_no_to_bool(protected_filter)
    if protected_value is not None:
        rows = rows.filter(protected=protected_value)
    else:
        protected_filter = ""

    if level_filter:
        try:
            rows = rows.filter(level=int(level_filter))
        except (TypeError, ValueError):
            level_filter = ""

    if search_query:
        rows = rows.filter(
            Q(name__icontains=search_query)
            | Q(path__icontains=search_query)
            | Q(label__icontains=search_query)
        )

    if sort_by not in VALID_CATEGORY_SORTS:
        sort_by = "path"

    rows = rows.order_by(sort_by)
    return rows, protected_filter, level_filter, search_query, sort_by


def _build_users_workspace_queryset(request: HttpRequest):
    User = get_user_model()
    users = User.objects.select_related("profile").prefetch_related("groups")
    staff_filter = request.GET.get("staff", "").strip()
    active_filter = request.GET.get("active", "").strip()
    superuser_filter = request.GET.get("superuser", "").strip()
    search_query = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort", "-date_joined").strip() or "-date_joined"

    staff_value = _yes_no_to_bool(staff_filter)
    if staff_value is not None:
        users = users.filter(is_staff=staff_value)
    else:
        staff_filter = ""

    active_value = _yes_no_to_bool(active_filter)
    if active_value is not None:
        users = users.filter(is_active=active_value)
    else:
        active_filter = ""

    superuser_value = _yes_no_to_bool(superuser_filter)
    if superuser_value is not None:
        users = users.filter(is_superuser=superuser_value)
    else:
        superuser_filter = ""

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(profile__display_name__icontains=search_query)
            | Q(profile__location__icontains=search_query)
        )

    if sort_by not in VALID_USER_SORTS:
        sort_by = "-date_joined"

    users = users.order_by(sort_by)
    return users, staff_filter, active_filter, superuser_filter, search_query, sort_by


def _build_groups_workspace_queryset(request: HttpRequest):
    groups = Group.objects.annotate(
        user_count=Count("user", distinct=True),
        permission_count=Count("permissions", distinct=True),
    )
    has_users_filter = request.GET.get("has_users", "").strip()
    search_query = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort", "name").strip() or "name"

    has_users_value = _yes_no_to_bool(has_users_filter)
    if has_users_value is True:
        groups = groups.filter(user_count__gt=0)
    elif has_users_value is False:
        groups = groups.filter(user_count=0)
    else:
        has_users_filter = ""

    if search_query:
        groups = groups.filter(name__icontains=search_query)

    if sort_by not in VALID_GROUP_SORTS:
        sort_by = "name"

    groups = groups.order_by(sort_by)
    return groups, has_users_filter, search_query, sort_by


@staff_member_required
@require_http_methods(["GET"])
def admin_pages_list(request: HttpRequest) -> HttpResponse:
    pages, status_filter, template_filter, nav_filter, search_query, sort_by = (
        _build_pages_workspace_queryset(request)
    )
    page_obj = Paginator(pages, PAGES_PAGE_SIZE).get_page(request.GET.get("page", 1))
    context = {
        "page_obj": page_obj,
        "pages": page_obj.object_list,
        "status_filter": status_filter,
        "template_filter": template_filter,
        "nav_filter": nav_filter,
        "search_query": search_query,
        "sort_by": sort_by,
        "status_choices": Page.Status.choices,
        "template_choices": Page.TemplateKey.choices,
        "is_paginated": page_obj.has_other_pages(),
        "page_query": _query_without_page(request),
        "total_pages": Page.objects.count(),
        "published_pages": Page.objects.filter(status=Page.Status.PUBLISHED).count(),
        "draft_pages": Page.objects.filter(status=Page.Status.DRAFT).count(),
        "review_pages": Page.objects.filter(status=Page.Status.REVIEW).count(),
        "archived_pages": Page.objects.filter(status=Page.Status.ARCHIVED).count(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "admin/pages/table.html", context)
    return render(request, "admin/pages/list.html", context)


@staff_member_required
@require_http_methods(["POST"])
def admin_pages_bulk_action(request: HttpRequest) -> HttpResponse:
    action = (request.POST.get("bulk_action") or "").strip().lower()
    selected_ids = _clean_post_ids(request.POST.getlist("selected_pages"))

    if not selected_ids:
        messages.warning(request, "Select at least one page.")
        return _redirect_next(request, "admin_pages_list")

    queryset = Page.objects.filter(id__in=selected_ids)
    if not queryset.exists():
        messages.warning(request, "No matching pages found.")
        return _redirect_next(request, "admin_pages_list")

    now = timezone.now()
    needs_seo_refresh = False

    if action == "publish":
        count = queryset.update(status=Page.Status.PUBLISHED, published_at=now, updated_at=now)
        messages.success(request, f"{count} pages published.")
        needs_seo_refresh = True
    elif action == "review":
        count = queryset.update(status=Page.Status.REVIEW, updated_at=now)
        messages.success(request, f"{count} pages moved to review.")
        needs_seo_refresh = True
    elif action == "archive":
        count = queryset.update(status=Page.Status.ARCHIVED, updated_at=now)
        messages.success(request, f"{count} pages archived.")
        needs_seo_refresh = True
    elif action == "nav_on":
        count = queryset.update(show_in_navigation=True, updated_at=now)
        messages.success(request, f"{count} pages shown in navigation.")
        needs_seo_refresh = True
    elif action == "nav_off":
        count = queryset.update(show_in_navigation=False, updated_at=now)
        messages.success(request, f"{count} pages hidden from navigation.")
        needs_seo_refresh = True
    elif action == "feature_on":
        count = queryset.update(is_featured=True, updated_at=now)
        messages.success(request, f"{count} pages marked as featured.")
        needs_seo_refresh = True
    elif action == "feature_off":
        count = queryset.update(is_featured=False, updated_at=now)
        messages.success(request, f"{count} pages unfeatured.")
        needs_seo_refresh = True
    elif action == "template_default":
        count = queryset.update(template_key=Page.TemplateKey.DEFAULT, updated_at=now)
        messages.success(request, f"{count} pages set to Default template.")
        needs_seo_refresh = True
    elif action == "template_landing":
        count = queryset.update(template_key=Page.TemplateKey.LANDING, updated_at=now)
        messages.success(request, f"{count} pages set to Landing template.")
        needs_seo_refresh = True
    elif action == "template_docs":
        count = queryset.update(template_key=Page.TemplateKey.DOCUMENTATION, updated_at=now)
        messages.success(request, f"{count} pages set to Documentation template.")
        needs_seo_refresh = True
    elif action == "delete":
        protected = queryset.filter(slug__in=POLICY_SLUGS)
        deletable = queryset.exclude(slug__in=POLICY_SLUGS)
        deleted_count = deletable.count()
        if deleted_count:
            deletable.delete()
            messages.success(request, f"{deleted_count} pages deleted.")
        if protected.exists():
            messages.warning(request, "Policy pages are protected and were not deleted.")
    else:
        messages.error(request, "Invalid page bulk action.")
        return _redirect_next(request, "admin_pages_list")

    if needs_seo_refresh:
        try:
            audit_content_batch("page", selected_ids, trigger="save", run_autopilot=True)
        except Exception:
            logger.exception("SEO refresh failed after admin page bulk action '%s'.", action)

    return _redirect_next(request, "admin_pages_list")


@staff_member_required
@require_http_methods(["GET"])
def admin_tags_list(request: HttpRequest) -> HttpResponse:
    model = Post.tags.tag_model
    rows, protected_filter, search_query, sort_by = _build_flat_taxonomy_queryset(
        request, model=model, valid_sorts=VALID_FLAT_TAG_SORTS
    )
    page_obj = Paginator(rows, TAXONOMY_PAGE_SIZE).get_page(request.GET.get("page", 1))
    total_items = model.objects.count()
    protected_items = model.objects.filter(protected=True).count()
    used_items = model.objects.filter(count__gt=0).count()
    context = {
        "taxonomy_label": "Tags",
        "taxonomy_intro": "Manage keyword tags used across posts.",
        "add_url": reverse("admin:blog_tagulous_post_tags_add"),
        "change_url_name": "admin:blog_tagulous_post_tags_change",
        "bulk_action_url": reverse("admin_tags_bulk_action"),
        "selection_name": "selected_tags",
        "page_obj": page_obj,
        "items": page_obj.object_list,
        "protected_filter": protected_filter,
        "search_query": search_query,
        "sort_by": sort_by,
        "is_paginated": page_obj.has_other_pages(),
        "page_query": _query_without_page(request),
        "total_items": total_items,
        "protected_items": protected_items,
        "used_items": used_items,
        "unused_items": max(total_items - used_items, 0),
    }
    if request.headers.get("HX-Request"):
        return render(request, "admin/taxonomy/flat_table.html", context)
    return render(request, "admin/taxonomy/flat_list.html", context)


@staff_member_required
@require_http_methods(["GET"])
def admin_topics_list(request: HttpRequest) -> HttpResponse:
    model = Post.primary_topic.tag_model
    rows, protected_filter, search_query, sort_by = _build_flat_taxonomy_queryset(
        request, model=model, valid_sorts=VALID_FLAT_TAG_SORTS
    )
    page_obj = Paginator(rows, TAXONOMY_PAGE_SIZE).get_page(request.GET.get("page", 1))
    total_items = model.objects.count()
    protected_items = model.objects.filter(protected=True).count()
    used_items = model.objects.filter(count__gt=0).count()
    context = {
        "taxonomy_label": "Primary Topics",
        "taxonomy_intro": "Manage high-level thematic topics assigned to posts.",
        "add_url": reverse("admin:blog_tagulous_post_primary_topic_add"),
        "change_url_name": "admin:blog_tagulous_post_primary_topic_change",
        "bulk_action_url": reverse("admin_topics_bulk_action"),
        "selection_name": "selected_topics",
        "page_obj": page_obj,
        "items": page_obj.object_list,
        "protected_filter": protected_filter,
        "search_query": search_query,
        "sort_by": sort_by,
        "is_paginated": page_obj.has_other_pages(),
        "page_query": _query_without_page(request),
        "total_items": total_items,
        "protected_items": protected_items,
        "used_items": used_items,
        "unused_items": max(total_items - used_items, 0),
    }
    if request.headers.get("HX-Request"):
        return render(request, "admin/taxonomy/flat_table.html", context)
    return render(request, "admin/taxonomy/flat_list.html", context)


@staff_member_required
@require_http_methods(["GET"])
def admin_categories_list(request: HttpRequest) -> HttpResponse:
    # Post.categories is TagField(tree=True): its tag_model IS always a BaseTagTreeModel subclass.
    tree_model: type[BaseTagTreeModel] = Post.categories.tag_model  # type: ignore[assignment]
    rows, protected_filter, level_filter, search_query, sort_by = (
        _build_category_taxonomy_queryset(request, model=tree_model)
    )
    page_obj = Paginator(rows, TAXONOMY_PAGE_SIZE).get_page(request.GET.get("page", 1))
    deepest_level = tree_model.objects.aggregate(max_level=Max("level")).get("max_level") or 0

    # Annotate items with tree indentation for WordPress-style display
    items = list(page_obj.object_list)
    for item in items:
        item.indent_display = "\u2014 " * max(0, item.level - 1)  # type: ignore[attr-defined]
        item.delete_url = reverse("admin_category_delete", kwargs={"pk": item.pk})  # type: ignore[attr-defined]
        item.edit_form_url = reverse("admin_category_edit_form", kwargs={"pk": item.pk})  # type: ignore[attr-defined]

    context = {
        "page_obj": page_obj,
        "items": items,
        "protected_filter": protected_filter,
        "level_filter": level_filter,
        "search_query": search_query,
        "sort_by": sort_by,
        "bulk_action_url": reverse("admin_categories_bulk_action"),
        "merge_url": reverse("admin_categories_merge"),
        "create_url": reverse("admin_category_create"),
        "selection_name": "selected_categories",
        "is_paginated": page_obj.has_other_pages(),
        "page_query": _query_without_page(request),
        "total_items": tree_model.objects.count(),
        "protected_items": tree_model.objects.filter(protected=True).count(),
        "root_items": tree_model.objects.filter(parent__isnull=True).count(),
        "used_items": tree_model.objects.filter(count__gt=0).count(),
        "deepest_level": deepest_level,
        "level_choices": range(1, max(deepest_level, 1) + 1),
        "reparent_url": reverse("admin_categories_reparent"),
        "category_max_depth": get_category_max_depth(),
        "parent_choices": _parent_choices(tree_model),
        "all_categories": list(tree_model.objects.order_by("name").values_list("pk", "label")),
    }
    if request.headers.get("HX-Request"):
        return render(request, "admin/taxonomy/categories_table.html", context)
    return render(request, "admin/taxonomy/categories_list.html", context)


@staff_member_required
@require_http_methods(["POST"])
def admin_categories_reparent(request: HttpRequest) -> JsonResponse:
    # Post.categories is TagField(tree=True): its tag_model IS always a BaseTagTreeModel subclass.
    tree_model: type[BaseTagTreeModel] = Post.categories.tag_model  # type: ignore[assignment]

    try:
        category_id = int((request.POST.get("category_id") or "").strip())
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Invalid category id."}, status=400)

    raw_parent_id = (request.POST.get("parent_id") or "").strip()
    parent_id = None
    if raw_parent_id:
        try:
            parent_id = int(raw_parent_id)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "message": "Invalid parent id."}, status=400)

    category = get_object_or_404(tree_model, pk=category_id)
    parent = None
    if parent_id is not None:
        parent = get_object_or_404(tree_model, pk=parent_id)

    if parent and parent.pk == category.pk:
        return JsonResponse(
            {"ok": False, "message": "A category cannot be its own parent."},
            status=400,
        )

    if parent and parent.path.startswith(f"{category.path}/"):
        return JsonResponse(
            {"ok": False, "message": "A category cannot be moved under its descendant."},
            status=400,
        )

    target_name = f"{parent.name}/{category.label}" if parent else category.label
    if target_name == category.name:
        return JsonResponse({"ok": True, "message": "Category hierarchy is already up to date."})

    max_depth = get_category_max_depth()
    target_root_depth = (parent.level + 1) if parent else 1
    descendant_offsets = [desc.level - category.level for desc in category.get_descendants()]
    deepest_offset = max(descendant_offsets, default=0)
    deepest_result_depth = target_root_depth + deepest_offset
    if deepest_result_depth > max_depth:
        return JsonResponse(
            {
                "ok": False,
                "message": (
                    f"Move exceeds max category depth ({max_depth}). "
                    f"Deepest affected level would be {deepest_result_depth}."
                ),
            },
            status=400,
        )

    if tree_model.objects.exclude(pk=category.pk).filter(name__iexact=target_name).exists():
        return JsonResponse(
            {"ok": False, "message": "A category with the same target path already exists."},
            status=400,
        )

    category.name = target_name
    try:
        category.save()
    except IntegrityError:
        return JsonResponse(
            {"ok": False, "message": "Unable to move category due to a hierarchy conflict."},
            status=400,
        )

    parent_label = parent.name if parent else "top level"
    return JsonResponse(
        {
            "ok": True,
            "message": f"Moved '{category.label}' under {parent_label}.",
            "category_id": category.pk,
            "parent_id": parent.pk if parent else None,
            "path": category.path,
            "level": category.level,
        }
    )


def _handle_taxonomy_bulk_action(
    request: HttpRequest,
    *,
    model: type[BaseTagModel],
    selection_key: str,
    fallback_url_name: str,
    label: str,
) -> HttpResponse:
    action = (request.POST.get("bulk_action") or "").strip().lower()
    selected_ids = _clean_post_ids(request.POST.getlist(selection_key))

    if not selected_ids:
        messages.warning(request, f"Select at least one {label}.")
        return _redirect_next(request, fallback_url_name)

    queryset = model.objects.filter(id__in=selected_ids)
    if not queryset.exists():
        messages.warning(request, f"No matching {label} found.")
        return _redirect_next(request, fallback_url_name)

    if action == "protect":
        count = queryset.update(protected=True)
        messages.success(request, f"{count} {label} protected.")
    elif action == "unprotect":
        count = queryset.update(protected=False)
        messages.success(request, f"{count} {label} unprotected.")
    elif action == "delete":
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"{count} {label} deleted.")
    else:
        messages.error(request, "Invalid taxonomy bulk action.")
    return _redirect_next(request, fallback_url_name)


@staff_member_required
@require_http_methods(["POST"])
def admin_tags_bulk_action(request: HttpRequest) -> HttpResponse:
    return _handle_taxonomy_bulk_action(
        request,
        model=Post.tags.tag_model,
        selection_key="selected_tags",
        fallback_url_name="admin_tags_list",
        label="tags",
    )


@staff_member_required
@require_http_methods(["POST"])
def admin_topics_bulk_action(request: HttpRequest) -> HttpResponse:
    return _handle_taxonomy_bulk_action(
        request,
        model=Post.primary_topic.tag_model,
        selection_key="selected_topics",
        fallback_url_name="admin_topics_list",
        label="topics",
    )


@staff_member_required
@require_http_methods(["POST"])
def admin_categories_bulk_action(request: HttpRequest) -> HttpResponse:
    return _handle_taxonomy_bulk_action(
        request,
        model=Post.categories.tag_model,
        selection_key="selected_categories",
        fallback_url_name="admin_categories_list",
        label="categories",
    )


# --- WordPress-style inline category CRUD ------------------------------------


def _get_category_tree_model() -> type[BaseTagTreeModel]:
    """Return the Tagulous-generated category tree model."""
    return Post.categories.tag_model  # type: ignore[return-value]


def _parent_choices(tree_model: type[BaseTagTreeModel], *, exclude_pk: int | None = None) -> list[tuple[str, str]]:
    """Build parent dropdown choices for category forms."""
    qs = tree_model.objects.order_by("name")
    if exclude_pk is not None:
        # Exclude self and descendants to prevent cycles
        try:
            cat = tree_model.objects.get(pk=exclude_pk)
            exclude_ids = {exclude_pk, *cat.get_descendants().values_list("pk", flat=True)}
            qs = qs.exclude(pk__in=exclude_ids)
        except tree_model.DoesNotExist:
            pass
    choices: list[tuple[str, str]] = [("", " None (top level) ")]
    max_depth = get_category_max_depth()
    for cat in qs:
        if cat.level < max_depth:
            indent = "\u2014 " * (cat.level - 1)  # em-dash indentation
            choices.append((str(cat.pk), f"{indent}{cat.label}"))
    return choices


@staff_member_required
@require_http_methods(["POST"])
def admin_category_create(request: HttpRequest) -> HttpResponse:
    """Inline HTMX handler: create a new category."""
    tree_model = _get_category_tree_model()
    name = (request.POST.get("name") or "").strip()
    parent_id = (request.POST.get("parent") or "").strip()

    if not name:
        messages.error(request, "Category name is required.")
        return _redirect_next(request, "admin_categories_list")

    # Build full path name
    parent = None
    if parent_id:
        try:
            parent = tree_model.objects.get(pk=int(parent_id))
        except (TypeError, ValueError, tree_model.DoesNotExist):
            messages.error(request, "Invalid parent category.")
            return _redirect_next(request, "admin_categories_list")

    full_name = f"{parent.name}/{name}" if parent else name

    # Check depth
    max_depth = get_category_max_depth()
    target_level = (parent.level + 1) if parent else 1
    if target_level > max_depth:
        messages.error(request, f"Maximum category depth is {max_depth}.")
        return _redirect_next(request, "admin_categories_list")

    # Check duplicates
    if tree_model.objects.filter(name__iexact=full_name).exists():
        messages.error(request, f"Category '{full_name}' already exists.")
        return _redirect_next(request, "admin_categories_list")

    try:
        tree_model.objects.create(name=full_name)
        messages.success(request, f"Category '{name}' created successfully.")
    except IntegrityError:
        logger.warning("Category creation integrity error for '%s'.", full_name, exc_info=True)
        messages.error(request, f"Could not create category '{name}'. It may already exist.")

    return _redirect_next(request, "admin_categories_list")


@staff_member_required
@require_http_methods(["GET"])
def admin_category_edit_form(request: HttpRequest, pk: int) -> HttpResponse:
    """Return the inline edit row partial for a single category."""
    tree_model = _get_category_tree_model()
    category = get_object_or_404(tree_model, pk=pk)
    context = {
        "item": category,
        "parent_choices": _parent_choices(tree_model, exclude_pk=pk),
        "update_url": reverse("admin_category_update", kwargs={"pk": pk}),
    }
    return render(request, "admin/taxonomy/partials/_category_edit_row.html", context)


@staff_member_required
@require_http_methods(["POST"])
def admin_category_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Inline HTMX handler: update a category name/parent."""
    tree_model = _get_category_tree_model()
    category = get_object_or_404(tree_model, pk=pk)

    new_label = (request.POST.get("name") or "").strip()
    parent_id = (request.POST.get("parent") or "").strip()
    is_protected = request.POST.get("protected") == "on"

    if not new_label:
        messages.error(request, "Category name is required.")
        return _redirect_next(request, "admin_categories_list")

    # Determine new parent
    new_parent = None
    if parent_id:
        try:
            new_parent = tree_model.objects.get(pk=int(parent_id))
        except (TypeError, ValueError, tree_model.DoesNotExist):
            messages.error(request, "Invalid parent category.")
            return _redirect_next(request, "admin_categories_list")

    # Check for circular reference
    if new_parent and new_parent.pk == category.pk:
        messages.error(request, "A category cannot be its own parent.")
        return _redirect_next(request, "admin_categories_list")
    if new_parent and new_parent.path.startswith(f"{category.path}/"):
        messages.error(request, "A category cannot be moved under its own descendant.")
        return _redirect_next(request, "admin_categories_list")

    # Build full name
    new_full_name = f"{new_parent.name}/{new_label}" if new_parent else new_label

    # Check depth
    max_depth = get_category_max_depth()
    target_level = (new_parent.level + 1) if new_parent else 1
    descendant_offsets = [d.level - category.level for d in category.get_descendants()]
    deepest_offset = max(descendant_offsets, default=0)
    if target_level + deepest_offset > max_depth:
        messages.error(request, f"Move would exceed max depth ({max_depth}).")
        return _redirect_next(request, "admin_categories_list")

    # Check duplicates (exclude self)
    if tree_model.objects.exclude(pk=pk).filter(name__iexact=new_full_name).exists():
        messages.error(request, f"Category '{new_full_name}' already exists.")
        return _redirect_next(request, "admin_categories_list")

    try:
        category.name = new_full_name
        category.protected = is_protected  # type: ignore[attr-defined]  # Tagulous BaseTagTreeModel field
        category.save()
        messages.success(request, f"Category '{new_label}' updated.")
    except IntegrityError:
        logger.warning("Category update integrity error for pk=%s.", pk, exc_info=True)
        messages.error(request, "Could not update category due to a conflict.")

    return _redirect_next(request, "admin_categories_list")


@staff_member_required
@require_http_methods(["POST"])
def admin_category_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a single category (with optional cascade)."""
    tree_model = _get_category_tree_model()
    category = get_object_or_404(tree_model, pk=pk)

    if category.protected:  # type: ignore[attr-defined]  # Tagulous BaseTagTreeModel field
        messages.error(request, f"Category '{category.label}' is protected and cannot be deleted.")
        return _redirect_next(request, "admin_categories_list")

    label = category.label
    child_count = category.children.count()  # type: ignore[attr-defined]  # Tagulous reverse FK
    try:
        category.delete()
        msg = f"Category '{label}' deleted."
        if child_count:
            msg += f" ({child_count} child categories were also removed.)"
        messages.success(request, msg)
    except Exception:
        logger.warning("Category delete failed for pk=%s.", pk, exc_info=True)
        messages.error(request, f"Could not delete category '{label}'.")

    return _redirect_next(request, "admin_categories_list")


@staff_member_required
@require_http_methods(["POST"])
def admin_categories_merge(request: HttpRequest) -> HttpResponse:
    """Merge selected categories into a target category."""
    tree_model = _get_category_tree_model()
    target_id = (request.POST.get("merge_target") or "").strip()
    selected_ids = _clean_post_ids(request.POST.getlist("selected_categories"))

    if not target_id:
        messages.error(request, "Select a target category to merge into.")
        return _redirect_next(request, "admin_categories_list")

    try:
        target = tree_model.objects.get(pk=int(target_id))
    except (TypeError, ValueError, tree_model.DoesNotExist):
        messages.error(request, "Invalid merge target.")
        return _redirect_next(request, "admin_categories_list")

    # Remove target from selected if present
    merge_ids = [i for i in selected_ids if i != target.pk]
    if not merge_ids:
        messages.warning(request, "No categories to merge (target cannot merge with itself).")
        return _redirect_next(request, "admin_categories_list")

    sources = tree_model.objects.filter(pk__in=merge_ids)
    if not sources.exists():
        messages.warning(request, "No matching categories found.")
        return _redirect_next(request, "admin_categories_list")

    merged_count = sources.count()
    try:
        target.merge_tags(sources)  # type: ignore[attr-defined]  # Tagulous BaseTagModel method
        messages.success(request, f"Merged {merged_count} categories into '{target.label}'.")
    except Exception:
        logger.warning("Category merge failed into pk=%s.", target.pk, exc_info=True)
        messages.error(request, "Category merge failed.")

    return _redirect_next(request, "admin_categories_list")


@staff_member_required
@require_http_methods(["GET"])
def admin_users_list(request: HttpRequest) -> HttpResponse:
    users, staff_filter, active_filter, superuser_filter, search_query, sort_by = (
        _build_users_workspace_queryset(request)
    )
    page_obj = Paginator(users, USERS_PAGE_SIZE).get_page(request.GET.get("page", 1))
    for user in page_obj.object_list:
        try:
            profile = user.profile
        except Exception:
            profile = None
        if profile is not None:
            user.profile_display_name = profile.effective_name
            user.profile_location = profile.location
        else:
            user.profile_display_name = user.get_full_name() or user.username
            user.profile_location = ""

    User = get_user_model()
    context = {
        "page_obj": page_obj,
        "users": page_obj.object_list,
        "staff_filter": staff_filter,
        "active_filter": active_filter,
        "superuser_filter": superuser_filter,
        "search_query": search_query,
        "sort_by": sort_by,
        "is_paginated": page_obj.has_other_pages(),
        "page_query": _query_without_page(request),
        "total_users": User.objects.count(),
        "staff_users": User.objects.filter(is_staff=True).count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "superusers": User.objects.filter(is_superuser=True).count(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "admin/users/table.html", context)
    return render(request, "admin/users/list.html", context)


@staff_member_required
@require_http_methods(["POST"])
def admin_users_bulk_action(request: HttpRequest) -> HttpResponse:
    if not request.user.is_superuser:
        messages.error(request, "Superuser permission required for user bulk actions.")
        return _redirect_next(request, "admin_users_list")

    action = (request.POST.get("bulk_action") or "").strip().lower()
    selected_ids = _clean_post_ids(request.POST.getlist("selected_users"))
    if not selected_ids:
        messages.warning(request, "Select at least one user.")
        return _redirect_next(request, "admin_users_list")

    User = get_user_model()
    queryset = User.objects.filter(id__in=selected_ids)
    if not queryset.exists():
        messages.warning(request, "No matching users found.")
        return _redirect_next(request, "admin_users_list")

    if action == "activate":
        count = queryset.update(is_active=True)
        messages.success(request, f"{count} users activated.")
    elif action == "deactivate":
        if request.user.pk in selected_ids:
            queryset = queryset.exclude(pk=request.user.pk)
            messages.warning(request, "Your own account was excluded from deactivation.")
        count = queryset.update(is_active=False)
        messages.success(request, f"{count} users deactivated.")
    elif action == "grant_staff":
        count = queryset.update(is_staff=True)
        messages.success(request, f"{count} users granted staff access.")
    elif action == "revoke_staff":
        if request.user.pk in selected_ids:
            queryset = queryset.exclude(pk=request.user.pk)
            messages.warning(request, "Your own account was excluded from staff revocation.")
        count = queryset.update(is_staff=False)
        messages.success(request, f"{count} users revoked from staff access.")
    elif action == "delete":
        if request.user.pk in selected_ids:
            queryset = queryset.exclude(pk=request.user.pk)
            messages.warning(request, "Your own account was excluded from deletion.")
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"{count} users deleted.")
    else:
        messages.error(request, "Invalid user bulk action.")
    return _redirect_next(request, "admin_users_list")


@staff_member_required
@require_http_methods(["GET"])
def admin_groups_list(request: HttpRequest) -> HttpResponse:
    groups, has_users_filter, search_query, sort_by = _build_groups_workspace_queryset(
        request
    )
    page_obj = Paginator(groups, GROUPS_PAGE_SIZE).get_page(request.GET.get("page", 1))
    groups_summary = Group.objects.annotate(
        _user_count=Count("user", distinct=True),
        _permission_count=Count("permissions", distinct=True),
    )
    total_groups = Group.objects.count()
    groups_with_users = groups_summary.filter(_user_count__gt=0).count()
    groups_with_permissions = groups_summary.filter(_permission_count__gt=0).count()
    context = {
        "page_obj": page_obj,
        "groups": page_obj.object_list,
        "has_users_filter": has_users_filter,
        "search_query": search_query,
        "sort_by": sort_by,
        "is_paginated": page_obj.has_other_pages(),
        "page_query": _query_without_page(request),
        "total_groups": total_groups,
        "groups_with_users": groups_with_users,
        "groups_with_permissions": groups_with_permissions,
        "unassigned_groups": max(total_groups - groups_with_users, 0),
    }
    if request.headers.get("HX-Request"):
        return render(request, "admin/groups/table.html", context)
    return render(request, "admin/groups/list.html", context)


@staff_member_required
@require_http_methods(["POST"])
def admin_groups_bulk_action(request: HttpRequest) -> HttpResponse:
    if not request.user.is_superuser:
        messages.error(request, "Superuser permission required for group bulk actions.")
        return _redirect_next(request, "admin_groups_list")

    action = (request.POST.get("bulk_action") or "").strip().lower()
    selected_ids = _clean_post_ids(request.POST.getlist("selected_groups"))

    if not selected_ids:
        messages.warning(request, "Select at least one group.")
        return _redirect_next(request, "admin_groups_list")

    queryset = Group.objects.filter(id__in=selected_ids)
    if not queryset.exists():
        messages.warning(request, "No matching groups found.")
        return _redirect_next(request, "admin_groups_list")

    if action == "delete":
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"{count} groups deleted.")
    else:
        messages.error(request, "Invalid group bulk action.")
    return _redirect_next(request, "admin_groups_list")


@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_settings(request: HttpRequest) -> HttpResponse:
    """
    Unified site settings page.
    """
    controls = FeatureControlSettings.get_solo()
    appearance = SiteAppearanceSettings.get_solo()
    identity = SiteIdentitySettings.get_solo()
    seo_defaults = SeoSettings.get_solo()
    integrations = IntegrationSettings.get_solo()
    valid_presets = {choice[0] for choice in APPEARANCE_PRESET_CHOICES}

    active_section = (request.GET.get("section", "appearance") or "appearance").strip().lower()
    if active_section not in {
        "appearance",
        "branding",
        "verification",
        "seo",
        "comments",
        "features",
        "integrations",
    }:
        active_section = "appearance"

    def parse_int(name: str, default: int, *, min_value: int, max_value: int):
        if name not in request.POST:
            return default
        raw = (request.POST.get(name, "") or "").strip()
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
        return max(min(value, max_value), min_value)

    def parse_float(name: str, default: float, *, min_value: float, max_value: float):
        if name not in request.POST:
            return default
        raw = (request.POST.get(name, "") or "").strip()
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = default
        return max(min(value, max_value), min_value)

    def parse_checkbox(name: str, default: bool):
        if name not in request.POST:
            return default
        value = (request.POST.get(name, "") or "").strip().lower()
        return value in {"1", "true", "on", "yes"}

    if request.method == "POST":
        spam_threshold = parse_int(
            "spam_threshold",
            controls.comment_spam_threshold,
            min_value=1,
            max_value=100,
        )

        mode_value = request.POST.get("theme_mode", appearance.mode).strip().lower()
        if mode_value not in {
            SiteAppearanceSettings.Mode.LIGHT,
            SiteAppearanceSettings.Mode.DARK,
        }:
            mode_value = appearance.mode
        preset_value = request.POST.get("theme_preset", appearance.preset).strip()
        if preset_value not in valid_presets:
            preset_value = appearance.preset

        appearance.mode = mode_value
        appearance.preset = preset_value
        appearance.save(update_fields=["mode", "preset", "updated_at"])

        identity.site_name = request.POST.get("site_name", identity.site_name).strip()
        identity.site_tagline = request.POST.get("site_tagline", identity.site_tagline).strip()
        identity.admin_brand_name = request.POST.get(
            "admin_brand_name", identity.admin_brand_name
        ).strip()
        identity.brand_logo_url = request.POST.get(
            "brand_logo_url", identity.brand_logo_url
        ).strip()
        identity.brand_logo_dark_url = request.POST.get(
            "brand_logo_dark_url", identity.brand_logo_dark_url
        ).strip()
        identity.favicon_url = request.POST.get(
            "favicon_url",
            identity.favicon_url,
        ).strip()
        identity.favicon_dark_url = request.POST.get(
            "favicon_dark_url",
            identity.favicon_dark_url,
        ).strip()

        if parse_checkbox("clear_brand_logo_upload", False):
            identity.brand_logo_upload.delete(save=False)
            identity.brand_logo_upload = None  # type: ignore[assignment]
        if parse_checkbox("clear_brand_logo_dark_upload", False):
            identity.brand_logo_dark_upload.delete(save=False)
            identity.brand_logo_dark_upload = None  # type: ignore[assignment]
        if parse_checkbox("clear_favicon_upload", False):
            identity.favicon_upload.delete(save=False)
            identity.favicon_upload = None  # type: ignore[assignment]
        if parse_checkbox("clear_favicon_dark_upload", False):
            identity.favicon_dark_upload.delete(save=False)
            identity.favicon_dark_upload = None  # type: ignore[assignment]

        if "brand_logo_upload" in request.FILES:
            identity.brand_logo_upload = request.FILES["brand_logo_upload"]  # type: ignore[assignment]
        if "brand_logo_dark_upload" in request.FILES:
            identity.brand_logo_dark_upload = request.FILES["brand_logo_dark_upload"]  # type: ignore[assignment]
        if "favicon_upload" in request.FILES:
            identity.favicon_upload = request.FILES["favicon_upload"]  # type: ignore[assignment]
        if "favicon_dark_upload" in request.FILES:
            identity.favicon_dark_upload = request.FILES["favicon_dark_upload"]  # type: ignore[assignment]

        identity.default_author_display = request.POST.get(
            "default_author_display", identity.default_author_display
        ).strip()
        identity.support_email = request.POST.get("support_email", identity.support_email).strip()
        identity.contact_email = request.POST.get("contact_email", identity.contact_email).strip()
        identity.footer_notice = request.POST.get("footer_notice", identity.footer_notice).strip()
        identity.legal_company_name = request.POST.get(
            "legal_company_name", identity.legal_company_name
        ).strip()
        identity.homepage_cta_label = request.POST.get(
            "homepage_cta_label", identity.homepage_cta_label
        ).strip() or "Explore"
        identity.homepage_cta_url = request.POST.get(
            "homepage_cta_url", identity.homepage_cta_url
        ).strip() or "/"
        identity.save(
            update_fields=[
                "site_name",
                "site_tagline",
                "admin_brand_name",
                "brand_logo_url",
                "brand_logo_dark_url",
                "brand_logo_upload",
                "brand_logo_dark_upload",
                "favicon_url",
                "favicon_dark_url",
                "favicon_upload",
                "favicon_dark_upload",
                "default_author_display",
                "support_email",
                "contact_email",
                "footer_notice",
                "legal_company_name",
                "homepage_cta_label",
                "homepage_cta_url",
                "updated_at",
            ]
        )

        integrations.analytics_provider = request.POST.get(
            "analytics_provider",
            integrations.analytics_provider,
        ).strip()
        allowed_providers = {choice[0] for choice in IntegrationSettings.AnalyticsProvider.choices}
        if integrations.analytics_provider not in allowed_providers:
            integrations.analytics_provider = IntegrationSettings.AnalyticsProvider.NONE
        integrations.ga4_measurement_id = request.POST.get(
            "ga4_measurement_id",
            integrations.ga4_measurement_id,
        ).strip()
        integrations.gtm_container_id = request.POST.get(
            "gtm_container_id",
            integrations.gtm_container_id,
        ).strip()
        integrations.plausible_domain = request.POST.get(
            "plausible_domain",
            integrations.plausible_domain,
        ).strip()
        integrations.custom_analytics_snippet = request.POST.get(
            "custom_analytics_snippet",
            integrations.custom_analytics_snippet,
        ).strip()
        integrations.webhook_url = request.POST.get(
            "webhook_url",
            integrations.webhook_url,
        ).strip()
        integrations.webhook_secret = request.POST.get(
            "webhook_secret",
            integrations.webhook_secret,
        ).strip()
        integrations.smtp_sender_name = request.POST.get(
            "smtp_sender_name",
            integrations.smtp_sender_name,
        ).strip()
        integrations.smtp_sender_email = request.POST.get(
            "smtp_sender_email",
            integrations.smtp_sender_email,
        ).strip()
        integrations.save(
            update_fields=[
                "analytics_provider",
                "ga4_measurement_id",
                "gtm_container_id",
                "plausible_domain",
                "custom_analytics_snippet",
                "webhook_url",
                "webhook_secret",
                "smtp_sender_name",
                "smtp_sender_email",
                "updated_at",
            ]
        )

        controls.enable_comments = parse_checkbox("allow_comments", controls.enable_comments)
        controls.moderate_comments = parse_checkbox(
            "moderate_comments",
            controls.moderate_comments,
        )
        controls.comment_spam_threshold = spam_threshold
        controls.enable_newsletter = parse_checkbox(
            "enable_newsletter",
            controls.enable_newsletter,
        )
        controls.enable_reactions = parse_checkbox(
            "enable_reactions",
            controls.enable_reactions,
        )
        controls.enable_quick_preview = parse_checkbox(
            "enable_quick_preview",
            controls.enable_quick_preview,
        )
        controls.enable_public_api = parse_checkbox(
            "enable_public_api",
            controls.enable_public_api,
        )
        controls.enable_policy_pages = parse_checkbox(
            "enable_policy_pages",
            controls.enable_policy_pages,
        )
        controls.enable_sitemap = parse_checkbox(
            "enable_sitemap",
            controls.enable_sitemap,
        )
        controls.enable_user_registration = parse_checkbox(
            "enable_user_registration",
            controls.enable_user_registration,
        )
        controls.enable_auto_tagging = parse_checkbox(
            "enable_auto_tagging",
            controls.enable_auto_tagging,
        )
        controls.auto_tagging_max_tags = parse_int(
            "auto_tagging_max_tags",
            controls.auto_tagging_max_tags,
            min_value=1,
            max_value=25,
        )
        controls.auto_tagging_max_total_tags = parse_int(
            "auto_tagging_max_total_tags",
            controls.auto_tagging_max_total_tags,
            min_value=1,
            max_value=25,
        )
        controls.auto_tagging_max_categories = parse_int(
            "auto_tagging_max_categories",
            controls.auto_tagging_max_categories,
            min_value=1,
            max_value=10,
        )
        controls.category_max_depth = parse_int(
            "category_max_depth",
            getattr(controls, "category_max_depth", 5),
            min_value=1,
            max_value=10,
        )
        controls.auto_tagging_min_score = parse_float(
            "auto_tagging_min_score",
            controls.auto_tagging_min_score,
            min_value=0.0,
            max_value=10.0,
        )
        controls.maintenance_mode = parse_checkbox(
            "maintenance_mode",
            controls.maintenance_mode,
        )
        controls.read_only_mode = parse_checkbox(
            "read_only_mode",
            controls.read_only_mode,
        )
        controls.save(
            update_fields=[
                "enable_newsletter",
                "enable_reactions",
                "enable_comments",
                "moderate_comments",
                "comment_spam_threshold",
                "enable_quick_preview",
                "enable_public_api",
                "enable_policy_pages",
                "enable_sitemap",
                "enable_user_registration",
                "enable_auto_tagging",
                "auto_tagging_max_tags",
                "auto_tagging_max_total_tags",
                "auto_tagging_max_categories",
                "category_max_depth",
                "auto_tagging_min_score",
                "maintenance_mode",
                "read_only_mode",
                "updated_at",
            ]
        )
        messages.success(request, "Settings saved successfully.")
        if request.headers.get("HX-Request"):
            return HttpResponse("Saved", status=200)
        base_url = reverse("admin_settings")
        return redirect(f"{base_url}?section={active_section}")

    verification_checks = {
        "google": bool(seo_defaults.google_site_verification.strip()),
        "bing": bool(seo_defaults.bing_site_verification.strip()),
        "yandex": bool(seo_defaults.yandex_site_verification.strip()),
        "pinterest": bool(seo_defaults.pinterest_site_verification.strip()),
    }
    context = {
        "active_section": active_section,
        "controls": controls,
        "appearance": appearance,
        "appearance_presets": APPEARANCE_PRESET_CHOICES,
        "identity": identity,
        "seo_defaults": seo_defaults,
        "integrations": integrations,
        "verification_checks": verification_checks,
        "verification_ready_count": sum(1 for ready in verification_checks.values() if ready),
    }
    return render(request, "admin/settings.html", context)


@staff_member_required
@require_http_methods(["POST"])
def admin_settings_theme_toggle(request: HttpRequest) -> JsonResponse:
    appearance = SiteAppearanceSettings.get_solo()
    requested_mode = (request.POST.get("mode", "") or "").strip().lower()

    if requested_mode in {
        SiteAppearanceSettings.Mode.LIGHT,
        SiteAppearanceSettings.Mode.DARK,
    }:
        appearance.mode = requested_mode
    else:
        appearance.mode = (
            SiteAppearanceSettings.Mode.DARK
            if appearance.mode == SiteAppearanceSettings.Mode.LIGHT.value  # type: ignore[comparison-overlap]
            else SiteAppearanceSettings.Mode.LIGHT
        )

    appearance.save(update_fields=["mode", "updated_at"])

    # Invalidate the context-processor cache so the next page load
    # renders the correct mode in server-side HTML.
    cache.delete("blog_site_appearance_ctx_v1")

    return JsonResponse(
        {
            "mode": appearance.mode,
            "preset": appearance.preset,
            "css_variables": appearance.css_variables,
            "updated_at": appearance.updated_at.isoformat() if appearance.updated_at else "",
        }
    )
