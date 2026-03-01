from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django_htmx.http import HttpResponseClientRedirect
from tagulous.views import autocomplete

from comments.models import (
    Comment,
    NewsletterSubscriber,
    PostBookmark,
    PostLike,
    PostView,
)
from comments.moderation import evaluate_comment_risk
from core.integrations import emit_platform_webhook
from core.models import FeatureControlSettings, SiteAppearanceSettings
from core.session import SessionService
from core.utils import cache_feature_control_settings, rate_limit
from seo.services import audit_content_batch, seo_context_for_instance, seo_context_for_route

from .forms import CommentForm, MarkdownPreviewForm, NewsletterForm, PostForm
from .models import (
    Post,
    render_markdown_to_safe_html,
)
from .services import (
    apply_auto_taxonomy_to_post,
    apply_post_filters,
    get_dashboard_metrics,
    get_dashboard_post_queryset,
    get_listing_context,
    get_related_posts_algorithmic,
    get_search_suggestion_context,
    serialize_post_for_api,
)
from .ui_feedback import attach_ui_feedback

logger = logging.getLogger(__name__)
DASHBOARD_POSTS_PER_PAGE = 12
DASHBOARD_SORT_CHOICES = {
    "-updated_at": "Recently updated",
    "-created_at": "Newest created",
    "-published_at": "Newest published",
    "title": "Title A-Z",
    "-views_count": "Most views",
}


def _can_access_post(post, user):
    if user.is_authenticated and user == post.author:
        return True

    return (
        post.status == Post.Status.PUBLISHED
        and post.published_at is not None
        and post.published_at <= timezone.now()
    )


def _get_visible_post_or_404(slug, user):
    post = get_object_or_404(
        Post.objects.select_related("author", "primary_topic").prefetch_related(
            "tags",
            "categories",
            "comments__author",
        ),
        slug=slug,
    )
    if not _can_access_post(post, user):
        raise Http404("Post not available")
    return post


def _track_view(request: HttpRequest, post: Post) -> None:
    if SessionService.is_marked(request, "post_view", post.pk):
        return

    session_fingerprint = SessionService.fingerprint(request)
    Post.objects.filter(pk=post.pk).update(views_count=F("views_count") + 1)
    post.refresh_from_db(fields=["views_count"])
    PostView.objects.create(
        post=post,
        user=request.user if request.user.is_authenticated else None,
        session_key=session_fingerprint,
    )
    SessionService.mark(request, "post_view", post.pk)


def _reaction_state(post, user):
    if not user.is_authenticated:
        return {"liked": False, "bookmarked": False}

    return {
        "liked": PostLike.objects.filter(post=post, user=user).exists(),
        "bookmarked": PostBookmark.objects.filter(post=post, user=user).exists(),
    }


def _reaction_counts(post):
    # Use pre-calculated reaction counts if available (from with_reaction_counts() annotation)
    # This avoids N+1 queries when processing multiple posts
    if hasattr(post, 'like_total') and hasattr(post, 'bookmark_total') and hasattr(post, 'comment_total'):
        return {
            "like_total": post.like_total,
            "bookmark_total": post.bookmark_total,
            "comment_total": post.comment_total,
        }

    # Fallback to direct queries for single post views
    return {
        "like_total": PostLike.objects.filter(post=post).count(),
        "bookmark_total": PostBookmark.objects.filter(post=post).count(),
        "comment_total": post.comments.filter(is_approved=True).count(),
    }


def _is_card_reaction_request(request: HttpRequest) -> bool:
    return (request.POST.get("reaction_context") or "").strip().lower() == "card"


def _render_reaction_fragment(request: HttpRequest, post: Post, *, global_reactions_enabled: bool) -> HttpResponse:
    context = {
        "post": post,
        "global_reactions_enabled": global_reactions_enabled,
        **_reaction_counts(post),
        **_reaction_state(post, request.user),
    }
    if _is_card_reaction_request(request):
        return render(request, "blog/partials/post_card_reactions.html", context)
    return render(request, "blog/partials/reaction_bar.html", context)


def _refresh_auto_taxonomy_for_queryset(queryset):
    for item in queryset.prefetch_related("tags", "categories"):
        apply_auto_taxonomy_to_post(item)


def _can_manage_comments(post, user):
    return bool(user.is_authenticated and (user == post.author or user.is_staff))


def _can_edit_comment(comment, user):
    return bool(
        user.is_authenticated
        and (user == comment.author or user == comment.post.author or user.is_staff)
    )


def _get_comments_queryset_for_user(post, user):
    comments = post.comments.select_related("author")
    if _can_manage_comments(post, user):
        return comments
    if user.is_authenticated:
        return comments.filter(Q(is_approved=True) | Q(author=user))
    return comments.filter(is_approved=True)


def _render_listing(request: HttpRequest, forced_filters=None) -> HttpResponse:
    context = get_listing_context(request, forced_filters=forced_filters)
    context.update(get_search_suggestion_context(request.user, context.get("active_query", "")))
    controls = FeatureControlSettings.get_solo()
    context["newsletter_form"] = NewsletterForm() if controls.enable_newsletter else None
    context["api_posts_url"] = reverse("blog:api_posts")
    query_text = context.get("active_query", "").strip()
    title = "Ultimate Blog Feed"
    description = "Explore the latest blog posts, categories, tags, and trending content."
    if query_text:
        title = f"Search results for {query_text}"
        description = f"Search results and related posts for {query_text}."
    context.update(
        seo_context_for_route(
            request,
            route_type="listing",
            title=title,
            description=description,
        )
    )
    template_name = "blog/partials/feed_panel.html" if request.htmx else "blog/home.html"
    return render(request, template_name, context)


def home(request: HttpRequest) -> HttpResponse:
    return _render_listing(request)


@require_GET
def posts_by_tag(request: HttpRequest, tag_name: str) -> HttpResponse:
    return _render_listing(request, forced_filters={"tag": tag_name})


@require_GET
def posts_by_topic(request: HttpRequest, topic_name: str) -> HttpResponse:
    return _render_listing(request, forced_filters={"topic": topic_name})


@require_GET
def posts_by_category(request: HttpRequest, category_name: str) -> HttpResponse:
    return _render_listing(request, forced_filters={"category": category_name})


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    sort_by = (request.GET.get("sort") or "-updated_at").strip()
    if sort_by not in DASHBOARD_SORT_CHOICES:
        sort_by = "-updated_at"

    posts_qs = (
        get_dashboard_post_queryset(request.user)
        .with_reaction_counts()
        .prefetch_related("tags")
        .select_related("author")
        .order_by(sort_by)
    )
    page_obj = Paginator(posts_qs, DASHBOARD_POSTS_PER_PAGE).get_page(request.GET.get("page", 1))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    dashboard_scope = "all" if request.user.is_staff else "mine"
    context = {
        "posts": page_obj.object_list,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "page_query": query_params.urlencode(),
        "dashboard_scope": dashboard_scope,
        "sort_by": sort_by,
        "sort_choices": DASHBOARD_SORT_CHOICES,
        **get_dashboard_metrics(request.user),
    }
    return render(request, "blog/dashboard.html", context)


@login_required
@require_POST
def post_bulk_action(request: HttpRequest) -> HttpResponse:
    action = (request.POST.get("bulk_action") or "").strip()
    selected_ids = request.POST.getlist("selected_posts")

    feedback_level = "info"
    feedback_message = "No changes applied."

    if not selected_ids:
        messages.warning(request, "Select at least one post.")
        feedback_level = "warning"
        feedback_message = "Select at least one post."
        if request.htmx:
            response = HttpResponseClientRedirect(reverse("blog:dashboard"))
            return attach_ui_feedback(
                response,
                toast={"level": feedback_level, "message": feedback_message},
                inline={
                    "target": "dashboard-posts",
                    "level": feedback_level,
                    "message": feedback_message,
                },
            )
        return redirect("blog:dashboard")

    queryset = get_dashboard_post_queryset(request.user).filter(id__in=selected_ids)
    if not queryset.exists():
        messages.warning(request, "No matching posts found.")
        feedback_level = "warning"
        feedback_message = "No matching posts found."
        if request.htmx:
            response = HttpResponseClientRedirect(reverse("blog:dashboard"))
            return attach_ui_feedback(
                response,
                toast={"level": feedback_level, "message": feedback_message},
                inline={
                    "target": "dashboard-posts",
                    "level": feedback_level,
                    "message": feedback_message,
                },
            )
        return redirect("blog:dashboard")

    now = timezone.now()
    count = queryset.count()

    needs_seo_refresh = False
    if action == "publish":
        queryset.update(status=Post.Status.PUBLISHED, published_at=now, updated_at=now)
        _refresh_auto_taxonomy_for_queryset(queryset)
        messages.success(request, f"{count} posts published.")
        feedback_level = "success"
        feedback_message = f"{count} posts published."
        needs_seo_refresh = True
    elif action == "review":
        queryset.update(status=Post.Status.REVIEW, updated_at=now)
        _refresh_auto_taxonomy_for_queryset(queryset)
        messages.success(request, f"{count} posts moved to review.")
        feedback_level = "success"
        feedback_message = f"{count} posts moved to review."
        needs_seo_refresh = True
    elif action == "archive":
        queryset.update(status=Post.Status.ARCHIVED, updated_at=now)
        _refresh_auto_taxonomy_for_queryset(queryset)
        messages.success(request, f"{count} posts archived.")
        feedback_level = "success"
        feedback_message = f"{count} posts archived."
        needs_seo_refresh = True
    elif action == "feature_on":
        queryset.update(is_featured=True, updated_at=now)
        messages.success(request, f"{count} posts marked as featured.")
        feedback_level = "success"
        feedback_message = f"{count} posts marked as featured."
        needs_seo_refresh = True
    elif action == "feature_off":
        queryset.update(is_featured=False, updated_at=now)
        messages.success(request, f"{count} posts removed from featured.")
        feedback_level = "success"
        feedback_message = f"{count} posts removed from featured."
        needs_seo_refresh = True
    elif action == "comments_on":
        queryset.update(allow_comments=True, updated_at=now)
        messages.success(request, f"Comments enabled for {count} posts.")
        feedback_level = "success"
        feedback_message = f"Comments enabled for {count} posts."
        needs_seo_refresh = True
    elif action == "comments_off":
        queryset.update(allow_comments=False, updated_at=now)
        messages.success(request, f"Comments disabled for {count} posts.")
        feedback_level = "success"
        feedback_message = f"Comments disabled for {count} posts."
        needs_seo_refresh = True
    elif action == "reactions_on":
        queryset.update(allow_reactions=True, updated_at=now)
        messages.success(request, f"Reactions enabled for {count} posts.")
        feedback_level = "success"
        feedback_message = f"Reactions enabled for {count} posts."
        needs_seo_refresh = True
    elif action == "reactions_off":
        queryset.update(allow_reactions=False, updated_at=now)
        messages.success(request, f"Reactions disabled for {count} posts.")
        feedback_level = "success"
        feedback_message = f"Reactions disabled for {count} posts."
        needs_seo_refresh = True
    elif action == "delete":
        queryset.delete()
        messages.success(request, f"{count} posts deleted.")
        feedback_level = "success"
        feedback_message = f"{count} posts deleted."
    else:
        messages.error(request, "Unknown bulk action.")
        feedback_level = "error"
        feedback_message = "Unknown bulk action."

    if needs_seo_refresh:
        try:
            audit_content_batch("post", selected_ids, trigger="save", run_autopilot=True)
        except Exception:
            logger.exception("SEO refresh failed after post bulk action '%s'.", action)

    if request.htmx:
        response = HttpResponseClientRedirect(reverse("blog:dashboard"))
        return attach_ui_feedback(
            response,
            toast={"level": feedback_level, "message": feedback_message},
            inline={
                "target": "dashboard-posts",
                "level": feedback_level,
                "message": feedback_message,
            },
        )
    return redirect("blog:dashboard")


def post_detail(request: HttpRequest, slug: str) -> HttpResponse:
    post = _get_visible_post_or_404(slug, request.user)
    _track_view(request, post)
    controls = FeatureControlSettings.get_solo()

    comments = _get_comments_queryset_for_user(post, request.user)
    comment_form = CommentForm()

    related_posts = get_related_posts_algorithmic(
        request.user,
        limit=4,
        anchor_post=post,
    )

    context = {
        "post": post,
        "comments": comments,
        "comment_form": comment_form,
        "can_manage_comments": _can_manage_comments(post, request.user),
        "related_posts": related_posts,
        "global_reactions_enabled": controls.enable_reactions,
        **_reaction_state(post, request.user),
    }
    context.update(seo_context_for_instance(post, request=request))
    return render(request, "blog/post_detail.html", context)


@require_GET
def search_suggestions(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "")
    context = get_search_suggestion_context(request.user, query)
    return render(request, "blog/partials/search_suggestions.html", context)


@require_GET
def post_quick_preview(request: HttpRequest, slug: str) -> HttpResponse:
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_quick_preview:
        raise Http404("Quick preview is disabled.")
    post = _get_visible_post_or_404(slug, request.user)
    context = {
        "post": post,
    }
    return render(request, "blog/partials/quick_preview_content.html", context)


@login_required
def post_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()
            try:
                apply_auto_taxonomy_to_post(post)
            except Exception:
                logger.exception("Auto taxonomy failed during post_create for post_id=%s.", post.pk)
                messages.warning(
                    request,
                    "Post saved, but taxonomy automation failed. You can retry from edit.",
                )
            post.record_revision(editor=request.user, note="Initial save")
            emit_platform_webhook(
                "post.created",
                {
                    "post_id": post.id,
                    "slug": post.slug,
                    "author_id": request.user.id,
                    "status": post.status,
                },
            )

            messages.success(request, "Post created successfully.")
            if request.htmx:
                response = HttpResponseClientRedirect(post.get_absolute_url())
                return attach_ui_feedback(
                    response,
                    toast={"level": "success", "message": "Post created successfully."},
                    inline={
                        "target": "post-form",
                        "level": "success",
                        "message": "Post created successfully.",
                    },
                )
            return redirect(post)
    else:
        form = PostForm()

    return render(
        request,
        "blog/post_form.html",
        {
            "form": form,
            "mode": "Create",
            "preview_html": "",
        },
    )


@login_required
def post_update(request: HttpRequest, slug: str) -> HttpResponse:
    post = get_object_or_404(get_dashboard_post_queryset(request.user), slug=slug)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            changed_fields = list(form.changed_data)
            post = form.save(commit=False)
            post.save()
            form.save_m2m()
            try:
                apply_auto_taxonomy_to_post(post)
            except Exception:
                logger.exception("Auto taxonomy failed during post_update for post_id=%s.", post.pk)
                messages.warning(
                    request,
                    "Post saved, but taxonomy automation failed. You can retry later.",
                )
            emit_platform_webhook(
                "post.updated",
                {
                    "post_id": post.id,
                    "slug": post.slug,
                    "author_id": request.user.id,
                    "changed_fields": changed_fields,
                },
            )

            if changed_fields:
                note = f"Updated fields: {', '.join(changed_fields)}"
                post.record_revision(editor=request.user, note=note)

            messages.success(request, "Post updated successfully.")
            if request.htmx:
                response = HttpResponseClientRedirect(post.get_absolute_url())
                return attach_ui_feedback(
                    response,
                    toast={"level": "success", "message": "Post updated successfully."},
                    inline={
                        "target": "post-form",
                        "level": "success",
                        "message": "Post updated successfully.",
                    },
                )
            return redirect(post)
    else:
        form = PostForm(instance=post)

    return render(
        request,
        "blog/post_form.html",
        {
            "form": form,
            "mode": "Update",
            "post": post,
            "preview_html": post.body_html,
        },
    )


@login_required
def post_delete(request: HttpRequest, slug: str) -> HttpResponse:
    post = get_object_or_404(get_dashboard_post_queryset(request.user), slug=slug)

    if request.method == "POST":
        emit_platform_webhook(
            "post.deleted",
            {
                "post_id": post.id,
                "slug": post.slug,
                "author_id": request.user.id,
            },
        )
        post.delete()
        messages.success(request, "Post deleted.")
        return redirect("blog:dashboard")

    return render(request, "blog/post_confirm_delete.html", {"post": post})


@login_required
def post_revisions(request: HttpRequest, slug: str) -> HttpResponse:
    post = get_object_or_404(Post, slug=slug)
    if not (request.user == post.author or request.user.is_staff):
        raise Http404("Post not available")

    revisions = post.revisions.select_related("editor").all()
    return render(
        request,
        "blog/post_revisions.html",
        {
            "post": post,
            "revisions": revisions,
        },
    )


@login_required
@require_POST
def markdown_preview(request: HttpRequest) -> HttpResponse:
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_quick_preview:
        return HttpResponseBadRequest("Markdown preview is disabled.")
    form = MarkdownPreviewForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid markdown preview request")

    preview_html = render_markdown_to_safe_html(form.cleaned_data.get("body_markdown", ""))
    return render(
        request,
        "blog/partials/editor_preview.html",
        {
            "preview_html": preview_html,
        },
    )


@login_required
@require_POST
def comment_create(request: HttpRequest, slug: str) -> HttpResponse:
    post = _get_visible_post_or_404(slug, request.user)
    can_manage = _can_manage_comments(post, request.user)
    controls = FeatureControlSettings.get_solo()

    if not controls.enable_comments:
        response = HttpResponseBadRequest("Comments are disabled globally.")
        if request.htmx:
            attach_ui_feedback(
                response,
                toast={
                    "level": "error",
                    "message": "Comments are disabled globally.",
                },
                inline={
                    "target": "comments",
                    "level": "error",
                    "message": "Comments are disabled globally.",
                },
            )
        return response

    if not post.allow_comments:
        response = HttpResponseBadRequest("Comments are disabled for this post.")
        if request.htmx:
            attach_ui_feedback(
                response,
                toast={
                    "level": "error",
                    "message": "Comments are disabled for this post.",
                },
                inline={
                    "target": "comments",
                    "level": "error",
                    "message": "Comments are disabled for this post.",
                },
            )
        return response

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        moderation = evaluate_comment_risk(comment.body)
        risk_score = int(moderation["score"])
        risk_reasons = list(moderation["reasons"])
        threshold = int(getattr(controls, "comment_spam_threshold", 70) or 70)
        threshold = max(1, min(threshold, 100))
        score_requires_moderation = risk_score >= threshold
        explicit_moderation_enabled = controls.moderate_comments

        comment.moderation_score = risk_score
        comment.moderation_reasons = risk_reasons
        comment.is_approved = not (
            (explicit_moderation_enabled or score_requires_moderation)
            and not _can_manage_comments(post, request.user)
        )
        comment.save()
        emit_platform_webhook(
            "comment.created",
            {
                "comment_id": comment.id,
                "post_id": post.id,
                "author_id": request.user.id,
                "approved": comment.is_approved,
                "risk_score": risk_score,
            },
        )
        if comment.is_approved:
            messages.success(request, "Comment added.")
            toast_message = "Comment added."
            toast_level = "success"
        else:
            if score_requires_moderation and not explicit_moderation_enabled:
                queue_message = (
                    f"Comment queued by risk engine (score {risk_score}/{threshold})."
                )
            else:
                queue_message = "Comment submitted and is awaiting moderation."
            messages.info(request, queue_message)
            toast_message = queue_message
            toast_level = "info"

        comments = _get_comments_queryset_for_user(post, request.user)
        context = {
            "post": post,
            "comments": comments,
            "comment_form": CommentForm(),
            "can_manage_comments": can_manage,
        }
        if request.htmx:
            response = render(request, "blog/partials/comments_section.html", context)
            return attach_ui_feedback(
                response,
                toast={"level": toast_level, "message": toast_message},
                inline={
                    "target": "comments",
                    "level": toast_level,
                    "message": toast_message,
                },
            )
        return redirect(f"{post.get_absolute_url()}#comments")

    comments = _get_comments_queryset_for_user(post, request.user)
    error_message = "Unable to add comment."
    if form.errors:
        first_error = next(iter(form.errors.values()), [])
        if first_error:
            error_message = str(first_error[0])
    context = {
        "post": post,
        "comments": comments,
        "comment_form": form,
        "can_manage_comments": can_manage,
    }
    if request.htmx:
        response = render(request, "blog/partials/comments_section.html", context, status=400)
        return attach_ui_feedback(
            response,
            toast={"level": "error", "message": error_message},
            inline={
                "target": "comments",
                "level": "error",
                "message": error_message,
            },
        )

    return render(request, "blog/post_detail.html", context, status=400)


@login_required
@require_POST
def comment_update(request: HttpRequest, comment_id: int) -> HttpResponse:
    comment = get_object_or_404(Comment.objects.select_related("post"), id=comment_id)
    if not _can_edit_comment(comment, request.user):
        raise Http404("Comment not available")

    form = CommentForm(request.POST, instance=comment)
    if form.is_valid():
        form.save()
        emit_platform_webhook(
            "comment.updated",
            {
                "comment_id": comment.id,
                "post_id": comment.post_id,
                "editor_id": request.user.id,
            },
        )
        messages.success(request, "Comment updated.")
        feedback_level = "success"
        feedback_message = "Comment updated."
    else:
        messages.error(request, "Unable to update comment.")
        feedback_level = "error"
        feedback_message = "Unable to update comment."

    post = comment.post
    context = {
        "post": post,
        "comments": _get_comments_queryset_for_user(post, request.user),
        "comment_form": CommentForm(),
        "can_manage_comments": _can_manage_comments(post, request.user),
    }
    if request.htmx:
        response = render(request, "blog/partials/comments_section.html", context, status=200)
        return attach_ui_feedback(
            response,
            toast={"level": feedback_level, "message": feedback_message},
            inline={
                "target": "comments",
                "level": feedback_level,
                "message": feedback_message,
            },
        )
    return redirect(f"{post.get_absolute_url()}#comments")


@login_required
@require_POST
def comment_delete(request: HttpRequest, comment_id: int) -> HttpResponse:
    comment = get_object_or_404(Comment.objects.select_related("post"), id=comment_id)
    if not _can_edit_comment(comment, request.user):
        raise Http404("Comment not available")

    post = comment.post
    emit_platform_webhook(
        "comment.deleted",
        {
            "comment_id": comment.id,
            "post_id": post.id,
            "editor_id": request.user.id,
        },
    )
    comment.delete()
    messages.success(request, "Comment deleted.")

    context = {
        "post": post,
        "comments": _get_comments_queryset_for_user(post, request.user),
        "comment_form": CommentForm(),
        "can_manage_comments": _can_manage_comments(post, request.user),
    }
    if request.htmx:
        response = render(request, "blog/partials/comments_section.html", context, status=200)
        return attach_ui_feedback(
            response,
            toast={"level": "success", "message": "Comment deleted."},
            inline={
                "target": "comments",
                "level": "success",
                "message": "Comment deleted.",
            },
        )
    return redirect(f"{post.get_absolute_url()}#comments")


@login_required
@require_POST
def comment_bulk_action(request: HttpRequest, slug: str) -> HttpResponse:
    post = _get_visible_post_or_404(slug, request.user)
    if not _can_manage_comments(post, request.user):
        raise Http404("Comments not available")

    action = (request.POST.get("bulk_action") or "").strip()
    selected_ids = request.POST.getlist("selected_comments")
    queryset = post.comments.filter(id__in=selected_ids)

    feedback_level = "info"
    feedback_message = "No changes applied."

    if not selected_ids or not queryset.exists():
        messages.warning(request, "Select comments to apply bulk actions.")
        feedback_level = "warning"
        feedback_message = "Select comments to apply bulk actions."
    elif action == "approve":
        count = queryset.update(is_approved=True)
        messages.success(request, f"{count} comments approved.")
        feedback_level = "success"
        feedback_message = f"{count} comments approved."
    elif action == "unapprove":
        count = queryset.update(is_approved=False)
        messages.success(request, f"{count} comments unapproved.")
        feedback_level = "success"
        feedback_message = f"{count} comments unapproved."
    elif action == "delete":
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"{count} comments deleted.")
        feedback_level = "success"
        feedback_message = f"{count} comments deleted."
    else:
        messages.error(request, "Unknown comment bulk action.")
        feedback_level = "error"
        feedback_message = "Unknown comment bulk action."

    context = {
        "post": post,
        "comments": _get_comments_queryset_for_user(post, request.user),
        "comment_form": CommentForm(),
        "can_manage_comments": True,
    }
    if request.htmx:
        response = render(request, "blog/partials/comments_section.html", context, status=200)
        return attach_ui_feedback(
            response,
            toast={"level": feedback_level, "message": feedback_message},
            inline={
                "target": "comments",
                "level": feedback_level,
                "message": feedback_message,
            },
        )
    return redirect(f"{post.get_absolute_url()}#comments")


@login_required
@require_POST
def toggle_like(request: HttpRequest, slug: str) -> HttpResponse:
    post = _get_visible_post_or_404(slug, request.user)
    controls = FeatureControlSettings.get_solo()
    feedback_target = "global" if _is_card_reaction_request(request) else "reactions"
    if not controls.enable_reactions:
        response = HttpResponseBadRequest("Reactions are disabled globally.")
        if request.htmx:
            attach_ui_feedback(
                response,
                toast={
                    "level": "error",
                    "message": "Reactions are disabled globally.",
                },
                inline={
                    "target": feedback_target,
                    "level": "error",
                    "message": "Reactions are disabled globally.",
                },
            )
        return response

    if not post.allow_reactions:
        response = HttpResponseBadRequest("Reactions are disabled for this post.")
        if request.htmx:
            attach_ui_feedback(
                response,
                toast={
                    "level": "error",
                    "message": "Reactions are disabled for this post.",
                },
                inline={
                    "target": feedback_target,
                    "level": "error",
                    "message": "Reactions are disabled for this post.",
                },
            )
        return response

    like, created = PostLike.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()

    response = _render_reaction_fragment(
        request,
        post,
        global_reactions_enabled=controls.enable_reactions,
    )
    if request.htmx:
        return attach_ui_feedback(
            response,
            toast={
                "level": "success",
                "message": "Post liked." if created else "Like removed.",
            },
            inline={
                "target": feedback_target,
                "level": "success",
                "message": "Post liked." if created else "Like removed.",
            },
        )
    return response


@login_required
@require_POST
def toggle_bookmark(request: HttpRequest, slug: str) -> HttpResponse:
    post = _get_visible_post_or_404(slug, request.user)
    controls = FeatureControlSettings.get_solo()
    feedback_target = "global" if _is_card_reaction_request(request) else "reactions"
    if not controls.enable_reactions:
        response = HttpResponseBadRequest("Reactions are disabled globally.")
        if request.htmx:
            attach_ui_feedback(
                response,
                toast={
                    "level": "error",
                    "message": "Reactions are disabled globally.",
                },
                inline={
                    "target": feedback_target,
                    "level": "error",
                    "message": "Reactions are disabled globally.",
                },
            )
        return response

    if not post.allow_reactions:
        response = HttpResponseBadRequest("Reactions are disabled for this post.")
        if request.htmx:
            attach_ui_feedback(
                response,
                toast={
                    "level": "error",
                    "message": "Reactions are disabled for this post.",
                },
                inline={
                    "target": feedback_target,
                    "level": "error",
                    "message": "Reactions are disabled for this post.",
                },
            )
        return response

    bookmark, created = PostBookmark.objects.get_or_create(post=post, user=request.user)
    if not created:
        bookmark.delete()

    response = _render_reaction_fragment(
        request,
        post,
        global_reactions_enabled=controls.enable_reactions,
    )
    if request.htmx:
        return attach_ui_feedback(
            response,
            toast={
                "level": "success",
                "message": "Post bookmarked." if created else "Bookmark removed.",
            },
            inline={
                "target": feedback_target,
                "level": "success",
                "message": "Post bookmarked." if created else "Bookmark removed.",
            },
        )
    return response


@require_POST
def newsletter_subscribe(request: HttpRequest) -> HttpResponse:
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_newsletter:
        response = HttpResponseBadRequest("Newsletter subscription is disabled.")
        if request.htmx:
            return attach_ui_feedback(
                response,
                toast={"level": "error", "message": "Newsletter is currently disabled."},
                inline={
                    "target": "newsletter",
                    "level": "error",
                    "message": "Newsletter is currently disabled.",
                },
            )
        messages.error(request, "Newsletter is currently disabled.")
        return redirect(request.META.get("HTTP_REFERER", reverse("blog:home")))

    form = NewsletterForm(request.POST)

    status = "error"
    message = "Unable to subscribe."

    if form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        full_name = form.cleaned_data.get("full_name", "").strip()

        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "source": "site",
                "is_active": True,
            },
        )

        if created:
            status = "success"
            message = "Subscribed successfully."
            emit_platform_webhook(
                "newsletter.subscribed",
                {
                    "email": subscriber.email,
                    "full_name": subscriber.full_name,
                },
            )
        elif subscriber.is_active:
            status = "info"
            message = "You are already subscribed."
        else:
            subscriber.is_active = True
            if full_name:
                subscriber.full_name = full_name
            subscriber.save(update_fields=["is_active", "full_name", "updated_at"])
            status = "success"
            message = "Subscription reactivated."
            emit_platform_webhook(
                "newsletter.reactivated",
                {
                    "email": subscriber.email,
                    "full_name": subscriber.full_name,
                },
            )

    context = {
        "status": status,
        "message": message,
        "newsletter_form": NewsletterForm(),
    }

    if request.htmx:
        level_map = {
            "success": "success",
            "info": "info",
            "error": "error",
        }
        feedback_level = level_map.get(status, "info")
        response = render(request, "blog/partials/newsletter_panel.html", context)
        return attach_ui_feedback(
            response,
            toast={"level": feedback_level, "message": message},
            inline={
                "target": "newsletter",
                "level": feedback_level,
                "message": message,
            },
        )

    if status == "success":
        messages.success(request, message)
    elif status == "info":
        messages.info(request, message)
    else:
        messages.error(request, message)

    return redirect(request.META.get("HTTP_REFERER", reverse("blog:home")))


@require_GET
@rate_limit(max_calls=100, time_window_seconds=3600)
def api_posts(request: HttpRequest) -> JsonResponse:
    controls = cache_feature_control_settings()
    if not controls.enable_public_api:
        return JsonResponse({"detail": "Public API is disabled."}, status=403)

    params = request.GET.copy()

    queryset = (
        Post.objects.select_related("author", "primary_topic")
        .prefetch_related("tags", "categories")
        .visible_to(request.user)
    )
    queryset = apply_post_filters(queryset, params)

    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page = 1

    try:
        per_page = max(min(int(request.GET.get("per_page", "12")), 50), 1)
    except ValueError:
        per_page = 12

    start = (page - 1) * per_page
    end = start + per_page
    total = queryset.count()

    posts = list(queryset[start:end])

    return JsonResponse(
        {
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
                "generated_at": timezone.now().isoformat(),
            },
            "data": [serialize_post_for_api(post) for post in posts],
        }
    )


@login_required
@require_GET
def api_dashboard_stats(request: HttpRequest) -> JsonResponse:
    metrics = get_dashboard_metrics(request.user)
    metrics["dashboard_top_posts"] = [
        {
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "views_count": post.views_count,
            "updated_at": post.updated_at.isoformat(),
            "url": post.get_absolute_url(),
        }
        for post in metrics["dashboard_top_posts"]
    ]
    metrics["dashboard_latest_activity"] = [
        {
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "status": post.status,
            "updated_at": post.updated_at.isoformat(),
            "url": post.get_absolute_url(),
        }
        for post in metrics["dashboard_latest_activity"]
    ]
    return JsonResponse(metrics)


@require_GET
def api_appearance_state(request: HttpRequest) -> JsonResponse:
    appearance = SiteAppearanceSettings.get_solo()
    return JsonResponse(
        {
            "mode": appearance.mode,
            "preset": appearance.preset,
            "css_variables": appearance.css_variables,
            "updated_at": appearance.updated_at.isoformat() if appearance.updated_at else "",
        }
    )


@login_required
@require_GET
def dashboard_stats_stream(request: HttpRequest) -> JsonResponse:
    """
    Polling JSON endpoint for dashboard statistics.

    Previously implemented as a Server-Sent Events (SSE) stream, which blocked
    WSGI workers indefinitely via ``time.sleep(5)`` inside a generator.  SSE
    over WSGI is unsafe for production: each open connection occupies a thread
    for its entire lifetime, exhausting the worker pool under any load.

    This endpoint now returns a **single JSON snapshot** on each request.
    The client should poll it at the desired interval using HTMX:

        <div hx-get="{% url 'blog:dashboard_stats_stream' %}"
             hx-trigger="every 5s"
             hx-swap="none"
             @htmx:after-request="updateDashboardStats($event.detail.xhr.responseText)">
        </div>

    This is WSGI-safe and requires no persistent connection.
    """
    try:
        metrics = get_dashboard_metrics(request.user)
    except Exception:
        logger.exception("Error fetching dashboard metrics for stats endpoint")
        return JsonResponse({"error": "metrics_unavailable"}, status=500)

    top_posts = [
        {
            "id": post.id,
            "title": post.title,
            "views": post.views_count,
            "url": post.get_absolute_url(),
        }
        for post in metrics.get("dashboard_top_posts", [])[:3]
    ]

    payload = {
        "timestamp": timezone.now().isoformat(),
        "post_count": metrics.get("dashboard_post_count", 0),
        "published_count": metrics.get("dashboard_published_count", 0),
        "draft_count": metrics.get("dashboard_draft_count", 0),
        "total_views": metrics.get("dashboard_total_views", 0),
        "total_comments": metrics.get("dashboard_total_comments", 0),
        "total_likes": metrics.get("dashboard_total_likes", 0),
        "total_bookmarks": metrics.get("dashboard_total_bookmarks", 0),
        "recent_activity_count": metrics.get("dashboard_activity_count", 0),
        "top_posts": top_posts,
    }
    return JsonResponse(payload)




@require_GET
def topic_autocomplete(request: HttpRequest) -> HttpResponse:
    return autocomplete(request, Post.primary_topic.tag_model)


@require_GET
def tag_autocomplete(request: HttpRequest) -> HttpResponse:
    return autocomplete(request, Post.tags.tag_model)


@require_GET
def category_autocomplete(request: HttpRequest) -> HttpResponse:
    return autocomplete(request, Post.categories.tag_model)
