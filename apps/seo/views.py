from __future__ import annotations

import re
from typing import Any, cast

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from blog.models import Post
from blog.services import build_embedding_vector, cosine_similarity, get_related_posts_algorithmic
from pages.models import Page

from .models import SeoEngineSettings, TaxonomySynonymGroup
from .services import (
    approve_suggestion,
    audit_content,
    live_check,
    reject_suggestion,
    seo_overview_metrics,
)
from .synonyms import expand_terms

TOKEN_RE = re.compile(r"[a-zA-Z0-9]{2,}")


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def _token_set(text: str, *, scope: str = TaxonomySynonymGroup.Scope.ALL) -> set[str]:
    return expand_terms(_tokens(text), scope=scope, include_original=True)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _clip_passages(markdown_text: str, query_terms: set[str], *, limit: int = 2) -> list[str]:
    if not markdown_text:
        return []
    lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    if not lines:
        return []
    ranked: list[tuple[float, str]] = []
    for line in lines:
        line_tokens = _token_set(line)
        overlap = len(query_terms & line_tokens)
        if overlap == 0:
            continue
        score = overlap / max(len(query_terms), 1)
        ranked.append((score, line))
    ranked.sort(key=lambda row: (row[0], len(row[1])), reverse=True)
    if not ranked:
        return lines[:1]
    return [line for _score, line in ranked[:limit]]


def _freshness_score(updated_at: Any) -> float:
    if not updated_at:
        return 0.0
    days = max((timezone.now() - updated_at).days, 0)
    return max(0.0, 1.0 - (min(days, 365) / 365.0))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _render_live_check_panel(
    request: HttpRequest,
    *,
    content_type: str,
    payload: dict[str, Any] | None = None,
    error: str = "",
    status: int = 200,
) -> HttpResponse:
    data = payload or {}
    field_checks = data.get("field_checks", {})

    # Ensure all tracked fields have entries (empty = all passed for that field)
    _TRACKED_FIELDS = ("title", "slug", "meta_description", "canonical_url", "body_markdown", "meta_title")
    for f in _TRACKED_FIELDS:
        field_checks.setdefault(f, [])

    response = render(
        request,
        "seo/partials/live_check_panel.html",
        {
            "content_type": content_type,
            "live_check": data,
            "live_check_error": error,
            "field_checks": field_checks,
        },
        status=status,
    )
    return response


def _score_post(query_vector: list[float], query_tokens: set[str], post: Post, max_views: int) -> dict[str, Any]:
    tag_names = [tag.name for tag in post.tags.all()]
    category_names = [category.name for category in post.categories.all()]
    topic_name = post.primary_topic.name if post.primary_topic else ""
    doc_text = " ".join(
        part
        for part in [
            post.title,
            post.excerpt,
            topic_name,
            " ".join(tag_names),
            " ".join(category_names),
            (post.body_markdown or "")[:2400],
        ]
        if part
    )
    doc_vector = build_embedding_vector(doc_text)
    semantic = max(min((cosine_similarity(query_vector, doc_vector) + 1.0) / 2.0, 1.0), 0.0)
    lexical = _jaccard(query_tokens, _token_set(doc_text))
    taxonomy_tokens = _token_set(" ".join(tag_names + category_names + ([topic_name] if topic_name else [])))
    taxonomy = _jaccard(query_tokens, taxonomy_tokens)
    behavior = min((post.views_count or 0) / max(max_views, 1), 1.0)
    freshness = _freshness_score(post.updated_at)
    total = (
        (0.55 * semantic)
        + (0.20 * lexical)
        + (0.10 * taxonomy)
        + (0.10 * behavior)
        + (0.05 * freshness)
    )
    return {
        "id": post.pk,
        "type": "post",
        "title": post.title,
        "url": post.get_absolute_url(),
        "excerpt": post.excerpt,
        "matched_passages": _clip_passages(post.body_markdown or "", query_tokens),
        "scores": {
            "total": round(total, 5),
            "semantic": round(semantic, 5),
            "lexical": round(lexical, 5),
            "taxonomy": round(taxonomy, 5),
            "behavior": round(behavior, 5),
            "freshness": round(freshness, 5),
        },
    }


def _score_page(query_vector: list[float], query_tokens: set[str], page: Page) -> dict[str, Any]:
    doc_text = " ".join(
        part
        for part in [
            page.title,
            page.summary,
            page.nav_label,
            (page.body_markdown or "")[:2400],
        ]
        if part
    )
    doc_vector = build_embedding_vector(doc_text)
    semantic = max(min((cosine_similarity(query_vector, doc_vector) + 1.0) / 2.0, 1.0), 0.0)
    lexical = _jaccard(query_tokens, _token_set(doc_text))
    freshness = _freshness_score(page.updated_at)
    total = (
        (0.55 * semantic)
        + (0.20 * lexical)
        + (0.10 * 0.0)
        + (0.10 * 0.0)
        + (0.05 * freshness)
    )
    return {
        "id": page.pk,
        "type": "page",
        "title": page.title,
        "url": page.get_absolute_url(),
        "excerpt": page.summary,
        "matched_passages": _clip_passages(page.body_markdown or "", query_tokens),
        "scores": {
            "total": round(total, 5),
            "semantic": round(semantic, 5),
            "lexical": round(lexical, 5),
            "taxonomy": 0.0,
            "behavior": 0.0,
            "freshness": round(freshness, 5),
        },
    }


@require_GET
def search_semantic(request: HttpRequest) -> JsonResponse:
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"query": "", "count": 0, "results": []})

    limit = min(max(_safe_int(request.GET.get("limit", "12"), 12), 1), 50)
    query_vector = build_embedding_vector(query)
    query_tokens = _token_set(query)

    posts = list(
        Post.objects.visible_to(request.user)
        .select_related("author", "primary_topic")
        .prefetch_related("tags", "categories")
        .order_by("-published_at", "-updated_at")[:250]
    )
    pages = list(
        Page.objects.visible_to(request.user)
        .select_related("author")
        .order_by("-published_at", "-updated_at")[:250]
    )

    max_views = max([post.views_count for post in posts], default=1)
    rows = [_score_post(query_vector, query_tokens, post, max_views) for post in posts]
    rows.extend(_score_page(query_vector, query_tokens, page) for page in pages)
    rows.sort(key=lambda row: row["scores"]["total"], reverse=True)

    return JsonResponse(
        {
            "query": query,
            "count": len(rows[:limit]),
            "results": rows[:limit],
        }
    )


@require_GET
def related_semantic(request: HttpRequest, post_id: int) -> JsonResponse:
    anchor = get_object_or_404(
        Post.objects.visible_to(request.user).select_related("author", "primary_topic"),
        pk=post_id,
    )
    related: list[dict[str, Any]] = cast(
        "list[dict[str, Any]]",
        get_related_posts_algorithmic(
            request.user,
            anchor_post=anchor,
            limit=min(max(_safe_int(request.GET.get("limit", "8"), 8), 1), 20),
            with_explanations=True,
        ),
    )
    return JsonResponse(
        {
            "post": {
                "id": anchor.pk,
                "title": anchor.title,
                "url": anchor.get_absolute_url(),
            },
            "count": len(related),
            "results": [
                {
                    "id": item["post"].pk,  # type: ignore[union-attr]
                    "title": item["post"].title,  # type: ignore[union-attr]
                    "url": item["post"].get_absolute_url(),  # type: ignore[union-attr]
                    "recommendation_type": item["recommendation_type"],
                    "score": round(item["total_score"], 5),
                    "components": item["components"],
                    "explain": item["explain"],
                }
                for item in related
            ],
        }
    )


@login_required
@require_POST
def live_check_inline(request: HttpRequest, content_type: str) -> HttpResponse | JsonResponse:
    normalized_type = (content_type or "").strip().lower()
    if normalized_type not in {"post", "page"}:
        if request.headers.get("HX-Request"):
            return _render_live_check_panel(
                request,
                content_type=normalized_type,
                error="Unsupported content type for live SEO checks.",
                status=404,
            )
        return JsonResponse(
            {
                "ok": False,
                "error": "unsupported_content_type",
            },
            status=404,
        )

    settings = SeoEngineSettings.get_solo()
    if not settings.enable_checks or not settings.enable_live_checks:
        if request.headers.get("HX-Request"):
            return _render_live_check_panel(
                request,
                content_type=normalized_type,
                error="Live SEO checks are currently disabled by admin settings.",
                status=403,
            )
        return JsonResponse(
            {
                "ok": False,
                "error": "live_checks_disabled",
            },
            status=403,
        )

    payload = {
        "title": request.POST.get("title", ""),
        "slug": request.POST.get("slug", ""),
        "meta_title": request.POST.get("meta_title", ""),
        "meta_description": request.POST.get("meta_description", ""),
        "canonical_url": request.POST.get("canonical_url", ""),
        "body_markdown": request.POST.get("body_markdown", ""),
    }
    if normalized_type == "post":
        payload["excerpt"] = request.POST.get("excerpt", "")
    else:
        payload["summary"] = request.POST.get("summary", "")

    result = live_check(normalized_type, payload)

    if request.headers.get("HX-Request"):
        return _render_live_check_panel(
            request,
            content_type=normalized_type,
            payload=result,
        )
    return JsonResponse({"ok": True, **result})


@staff_member_required
@require_POST
def reindex_post(request: HttpRequest, post_id: int) -> JsonResponse:
    snapshot = audit_content("post", post_id, trigger="manual")
    if snapshot is None:
        return JsonResponse({"ok": False, "message": "Post not found."}, status=404)
    return JsonResponse(
        {
            "ok": True,
            "snapshot_id": snapshot.pk,
            "score": snapshot.score,
            "critical_count": snapshot.critical_count,
            "warning_count": snapshot.warning_count,
            "audited_at": snapshot.audited_at.isoformat(),
        }
    )


@staff_member_required
@require_POST
def review_approve(request: HttpRequest, candidate_id: int) -> JsonResponse:
    result = approve_suggestion(candidate_id, reviewer=request.user)
    status = result.pop("status", 200)
    return JsonResponse(result, status=status)


@staff_member_required
@require_POST
def review_reject(request: HttpRequest, candidate_id: int) -> JsonResponse:
    result = reject_suggestion(candidate_id)
    status = result.pop("status", 200)
    return JsonResponse(result, status=status)


@staff_member_required
@require_GET
def dashboard_stats(request: HttpRequest) -> JsonResponse:
    return JsonResponse(seo_overview_metrics())
