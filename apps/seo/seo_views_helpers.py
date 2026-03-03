"""
SEO Views — Private helper functions and constants.

All private utility functions used by the SEO admin control center views.
Split from admin_config_views.py for maintainability.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, cast

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

from blog.models import Post
from core.utils import ADMIN_PAGINATION_SIZE
from pages.models import Page

from .models import SeoIssue, SeoLinkEdge, SeoSuggestion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API — suppress "not accessed" warnings for cross-module imports
# ---------------------------------------------------------------------------
__all__ = [
    "ONSITE_SUGGESTIONS_PAGE_SIZE",
    "ONSITE_TASKS_PAGE_SIZE",
    "SEO_CONTROL_SECTIONS",
    "SEO_CONTROL_SECTION_ALIASES",
    "_admin_control_context",
    "_control_redirect",
    "_control_url",
    "_enriched_issue_feed",
    "_ensure_admin_control_enabled",
    "_interlink_edge_rows",
    "_interlink_metrics",
    "_interlink_suggestion_rows",
    "_normalize_control_section",
    "_open_issue_target_refs",
    "_paginate_rows",
    "_pending_tasks",
    "_query_without_keys",
    "_queue_counts_for_suggestions",
    "_queue_counts_from_rows",
    "_resolve_return_section",
    "_seo_issue_rows",
    "_suggestion_rows",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEO_CONTROL_SECTIONS = {
    "discrepancies",
    "interlinking",
    "metadata",
    "redirects",
    "settings",
    # Legacy sections — aliased to new tabs.
    "scan",
    "results",
    "onsite",
    "suggestions",
}
SEO_CONTROL_SECTION_ALIASES = {
    "suggestions": "discrepancies",
    "seo": "discrepancies",
    "onsite": "discrepancies",
    "scan": "discrepancies",
    "results": "discrepancies",
    "redirect": "redirects",
}
ONSITE_TASKS_PAGE_SIZE = ADMIN_PAGINATION_SIZE
ONSITE_SUGGESTIONS_PAGE_SIZE = ADMIN_PAGINATION_SIZE


# ---------------------------------------------------------------------------
# Private helper functions
# ---------------------------------------------------------------------------


def _ensure_admin_control_enabled() -> None:
    if not bool(getattr(settings, "ENABLE_ADMIN_CONTROL", True)):
        raise Http404("SEO Control is disabled.")


def _admin_control_context(
    *,
    section: str,
    title: str,
    subtitle: str = "",
    breadcrumb_parent_label: str = "",
    breadcrumb_parent_url: str = "",
) -> dict[str, Any]:
    return {
        "admin_control_enabled": True,
        "admin_control_section": section,
        "admin_control_title": title,
        "admin_control_subtitle": subtitle,
        "admin_control_breadcrumb_parent_label": breadcrumb_parent_label,
        "admin_control_breadcrumb_parent_url": breadcrumb_parent_url,
        "title": title,
    }


def _normalize_control_section(section: str | None, default: str = "discrepancies") -> str:
    safe = (section or "").strip().lower()
    safe = SEO_CONTROL_SECTION_ALIASES.get(safe, safe)
    return safe if safe in SEO_CONTROL_SECTIONS else default


def _control_url(section: str = "scan", **params: Any) -> str:
    safe_section = _normalize_control_section(section)
    base = reverse("admin_config:seo_control_canonical_section", kwargs={"section": safe_section})
    query_parts: list[str] = []
    for key, value in params.items():
        if value not in {None, ""}:
            query_parts.append(f"{key}={value}")
    suffix = f"?{'&'.join(query_parts)}" if query_parts else ""
    return f"{base}{suffix}"


def _control_redirect(section: str = "discrepancies", **params: Any) -> HttpResponseRedirect:
    return redirect(_control_url(section=section, **params))


def _query_without_keys(request: HttpRequest, *keys: str) -> str:
    query = request.GET.copy()
    for key in keys:
        query.pop(key, None)
    return query.urlencode()


def _resolve_return_section(request: HttpRequest, default: str = "onsite") -> str:
    raw = (
        request.POST.get("return_section")
        or request.GET.get("return_section")
        or request.GET.get("section")
    )
    return _normalize_control_section(raw, default=default)


def _workspace_admin_url(obj: object) -> str:
    """Generate custom admin workspace edit URL instead of Django admin change URL."""
    if isinstance(obj, Post):
        return reverse("admin_post_editor", kwargs={"post_id": obj.pk})
    if isinstance(obj, Page):
        try:
            return reverse("pages:update", kwargs={"slug": obj.slug})
        except Exception:
            logger.warning("Failed to reverse pages:update for slug=%s", obj.slug)
            return ""
    # Fallback to Django admin change URL
    try:
        return reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",  # type: ignore[union-attr]
            args=[obj.pk],  # type: ignore[union-attr]
        )
    except Exception:
        logger.warning("Failed to reverse admin change URL for %s", type(obj).__name__)
        return ""


def _suggestion_target(suggestion: SeoSuggestion) -> dict[str, str]:
    model = suggestion.content_type.model_class()
    if not model:
        return {"title": "Unknown", "public_url": "", "admin_url": ""}
    target = model.objects.filter(pk=suggestion.object_id).first()
    if not target:
        return {"title": "Deleted content", "public_url": "", "admin_url": ""}
    title = getattr(target, "title", "") or str(target)
    public_url = ""
    try:
        _get_url = getattr(target, "get_absolute_url", None)
        public_url = str(_get_url()) if callable(_get_url) else ""
    except Exception:
        public_url = ""
    admin_url = _workspace_admin_url(target)
    return {"title": title, "public_url": public_url, "admin_url": admin_url}


def _suggestion_rows(
    *,
    statuses: Sequence[str] | None = None,
    suggestion_types: Sequence[str] | None = None,
    exclude_suggestion_types: Sequence[str] | None = None,
    limit: int | None = 250,
) -> list[dict[str, Any]]:
    queryset = SeoSuggestion.objects.select_related("content_type").order_by("-created_at")
    if statuses:
        queryset = queryset.filter(status__in=statuses)
    if suggestion_types:
        queryset = queryset.filter(suggestion_type__in=suggestion_types)
    if exclude_suggestion_types:
        queryset = queryset.exclude(suggestion_type__in=exclude_suggestion_types)
    rows: list[dict[str, Any]] = []
    if limit is None:
        iterator = queryset
    else:
        iterator = queryset[:limit]
    for suggestion in iterator:
        target = _suggestion_target(suggestion)
        rows.append(
            {
                "id": suggestion.pk,
                "status": suggestion.status,
                "type": suggestion.suggestion_type,
                "confidence": suggestion.confidence,
                "created_at": suggestion.created_at,
                "payload_json": cast("dict[str, Any]", suggestion.payload_json),  # type: ignore[reportUnknownMemberType]
                "target_title": target["title"],
                "target_public_url": target["public_url"],
                "target_admin_url": target["admin_url"],
                "object_id": suggestion.object_id,
                "content_type_id": suggestion.content_type.pk,
                "content_model": suggestion.content_type.model,
            }
        )
    return rows


def _suggestion_task_row(suggestion: SeoSuggestion) -> dict[str, Any]:
    target = _suggestion_target(suggestion)
    payload: dict[str, Any] = cast("dict[str, Any]", suggestion.payload_json or {})  # type: ignore[reportUnknownMemberType]
    suggestion_type: str = suggestion.suggestion_type
    if suggestion_type == "metadata":
        domain = "metadata"
    elif suggestion_type == "interlink":
        domain = "internal_linking"
    else:
        domain = "seo"
    priority = "high" if suggestion.confidence >= 0.85 else "medium" if suggestion.confidence >= 0.6 else "low"

    if suggestion_type == "metadata":
        title = "Metadata enhancement"
        description = "Update meta title/description/canonical values for stronger SERP presentation."
        recommendation = (
            "Validate metadata intent alignment. Approve if title/description are accurate and non-duplicative."
        )
        evidence = (
            f"title={str(payload.get('meta_title', ''))[:70]} | "
            f"description={str(payload.get('meta_description', ''))[:120]}"
        )
    elif suggestion_type == "interlink":
        anchor: str = str(payload.get("anchor_text") or "").strip()
        target_url: str = str(payload.get("target_url") or "").strip()
        description = (
            f"Insert internal link from anchor '{anchor or 'N/A'}' to '{target_url or 'N/A'}'."
        )
        title = "Internal link insertion"
        recommendation = (
            "Approve only if anchor appears naturally in body text and target destination is contextually relevant."
        )
        evidence = f"score={float(payload.get('score', 0.0) or 0.0):.3f} | target={target_url or 'N/A'}"
    else:
        old_path: str = str(payload.get("old_path") or "").strip()
        target_url = str(payload.get("suggested_target") or "").strip()
        status_code: int = int(payload.get("status_code", 301) or 301)
        title = "Redirect rule"
        description = f"Add redirect for '{old_path or 'N/A'}' to '{target_url or '/'}'."
        recommendation = (
            "Approve to preserve crawl continuity and prevent broken-path indexing where redirect is valid."
        )
        evidence = f"status_code={status_code}"

    return {
        "task_kind": "suggestion",
        "task_ref": f"S-{suggestion.pk}",
        "id": suggestion.pk,
        "domain": domain,
        "priority": priority,
        "status": suggestion.status,
        "type_label": str(getattr(suggestion, "get_suggestion_type_display", lambda: "")()),
        "title": title,
        "description": description,
        "recommendation": recommendation,
        "evidence": evidence,
        "confidence": suggestion.confidence,
        "created_at": suggestion.created_at,
        "target_title": target["title"],
        "target_admin_url": target["admin_url"],
        "target_public_url": target["public_url"],
        "target_content_type_id": suggestion.content_type.pk,
        "target_object_id": suggestion.object_id,
        "suggestion_id": suggestion.pk,
    }


def _issue_domain(check_key: str) -> str:
    lower_key = (check_key or "").strip().lower()
    if any(token in lower_key for token in {"internal", "link", "anchor", "orphan"}):
        return "internal_linking"
    return "seo"


def _open_issue_target_refs(*, domain: str | None = None) -> set[tuple[int, int]]:
    refs: set[tuple[int, int]] = set()
    queryset = (
        SeoIssue.objects.select_related("snapshot")
        .filter(status=SeoIssue.Status.OPEN)
        .order_by("-created_at")
    )
    for issue in queryset:
        issue_domain = _issue_domain(issue.check_key)
        if domain and issue_domain != domain:
            continue
        ct_id: int = int(getattr(issue.snapshot, "content_type_id", 0))
        refs.add((ct_id, issue.snapshot.object_id))
    return refs


def _issue_task_row(issue: SeoIssue) -> dict[str, Any]:
    check_key = (issue.check_key or "").strip()
    domain = _issue_domain(check_key)
    severity: str = (issue.severity or "").lower()
    priority = "high" if severity == "critical" else "medium"
    suggestion_text = (issue.suggested_fix or "").strip() or "Review content and apply a manual fix, then rescan."
    evidence_url = getattr(issue.snapshot, "url", "") or ""

    # Resolve admin + public URLs from the snapshot's content reference
    ref_cache: dict[tuple[int, int], dict[str, str]] = {}
    snapshot = issue.snapshot
    ref = _resolve_content_ref(ref_cache, snapshot.content_type, snapshot.object_id)
    target_title = ref["title"] or evidence_url or "Content snapshot"
    target_admin_url = ref["admin_url"]
    target_public_url = ref["public_url"] or evidence_url

    return {
        "task_kind": "issue",
        "task_ref": f"I-{issue.pk}",
        "id": issue.pk,
        "domain": domain,
        "priority": priority,
        "status": issue.status,
        "type_label": "Issue",
        "title": check_key.replace("_", " ").title() if check_key else "SEO issue",
        "description": issue.message,
        "recommendation": suggestion_text,
        "evidence": evidence_url or "Snapshot evidence available in issue feed.",
        "confidence": None,
        "created_at": issue.created_at,
        "target_title": target_title,
        "target_admin_url": target_admin_url,
        "target_public_url": target_public_url,
        "target_content_type_id": int(getattr(snapshot, "content_type_id", 0)),
        "target_object_id": snapshot.object_id,
        "suggestion_id": None,
    }


def _resolve_content_ref(
    cache: dict[tuple[int, int], dict[str, str]],
    content_type: Any,
    object_id: int,
) -> dict[str, str]:
    if not content_type:
        return {"title": "Unknown", "admin_url": "", "public_url": ""}
    cache_key = (content_type.pk, int(object_id))
    if cache_key in cache:
        return cache[cache_key]
    model = content_type.model_class()
    if not model:
        cache[cache_key] = {"title": "Unknown", "admin_url": "", "public_url": ""}
        return cache[cache_key]
    obj = model.objects.filter(pk=object_id).first()
    if not obj:
        cache[cache_key] = {"title": "Deleted content", "admin_url": "", "public_url": ""}
        return cache[cache_key]
    title = getattr(obj, "title", "") or str(obj)
    admin_url = _workspace_admin_url(obj)
    try:
        _get_url = getattr(obj, "get_absolute_url", None)
        public_url = str(_get_url()) if callable(_get_url) else ""
    except Exception:
        public_url = ""
    cache[cache_key] = {
        "title": title,
        "admin_url": admin_url,
        "public_url": public_url,
    }
    return cache[cache_key]


def _interlink_edge_rows(limit: int = 220) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ref_cache: dict[tuple[int, int], dict[str, str]] = {}
    queryset = (
        SeoLinkEdge.objects.select_related("source_content_type", "target_content_type")
        .order_by("-created_at")[:limit]
    )
    for edge in queryset:
        source = _resolve_content_ref(ref_cache, edge.source_content_type, edge.source_object_id)
        target = _resolve_content_ref(ref_cache, edge.target_content_type, edge.target_object_id)
        rows.append(
            {
                "id": edge.pk,
                "status": edge.status,
                "confidence": edge.confidence,
                "anchor_text": edge.anchor_text,
                "created_at": edge.created_at,
                "source_title": source["title"],
                "source_admin_url": source["admin_url"],
                "source_public_url": source["public_url"],
                "target_title": target["title"],
                "target_admin_url": target["admin_url"],
                "target_public_url": target["public_url"],
            }
        )
    return rows


def _interlink_suggestion_rows(limit: int = 220) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ref_cache: dict[tuple[int, int], dict[str, str]] = {}
    queryset = (
        SeoSuggestion.objects.select_related("content_type")
        .filter(
            suggestion_type=SeoSuggestion.SuggestionType.INTERLINK,
            status__in=[SeoSuggestion.Status.PENDING, SeoSuggestion.Status.NEEDS_CORRECTION],
        )
        .order_by("-confidence", "-created_at")[:limit]
    )
    for suggestion in queryset:
        payload: dict[str, Any] = cast("dict[str, Any]", suggestion.payload_json or {})  # type: ignore[reportUnknownMemberType]
        source = _resolve_content_ref(ref_cache, suggestion.content_type, suggestion.object_id)
        target_title = payload.get("target_title", "") or payload.get("target_url", "") or "Target"
        target_admin_url = ""
        target_public_url = payload.get("target_url", "")
        target_type = (payload.get("target_type") or "").strip()
        target_id = payload.get("target_id")
        if target_type in {"post", "page"} and str(target_id or "").isdigit():
            target_model = Post if target_type == "post" else Page
            target_ct = ContentType.objects.get_for_model(target_model)
            target = _resolve_content_ref(ref_cache, target_ct, int(target_id or 0))
            target_title = target["title"]
            target_admin_url = target["admin_url"]
            target_public_url = target["public_url"] or target_public_url
        rows.append(
            {
                "id": suggestion.pk,
                "status": suggestion.status,
                "confidence": suggestion.confidence,
                "created_at": suggestion.created_at,
                "anchor_text": payload.get("anchor_text", ""),
                "score": float(payload.get("score", 0.0) or 0.0),
                "source_title": source["title"],
                "source_admin_url": source["admin_url"],
                "source_public_url": source["public_url"],
                "target_title": target_title,
                "target_admin_url": target_admin_url,
                "target_public_url": target_public_url,
            }
        )
    return rows


def _seo_issue_rows(limit: int = 220) -> list[SeoIssue]:
    rows: list[SeoIssue] = []
    queryset = (
        SeoIssue.objects.select_related("snapshot")
        .filter(status=SeoIssue.Status.OPEN)
        .order_by("-created_at")
    )
    for issue in queryset:
        if _issue_domain(issue.check_key) != "seo":
            continue
        rows.append(issue)
        if len(rows) >= limit:
            break
    return rows


def _enriched_issue_feed(limit: int = 40) -> list[dict[str, Any]]:
    """Return open issues with resolved target admin + public URLs."""
    ref_cache: dict[tuple[int, int], dict[str, str]] = {}
    enriched: list[dict[str, Any]] = []
    queryset = (
        SeoIssue.objects.select_related("snapshot", "snapshot__content_type")
        .filter(status=SeoIssue.Status.OPEN)
        .order_by("-created_at")[:limit]
    )
    for issue in queryset:
        snapshot = issue.snapshot
        ref = _resolve_content_ref(ref_cache, snapshot.content_type, snapshot.object_id)
        enriched.append({
            "severity": issue.severity,
            "check_key": issue.check_key,
            "message": issue.message,
            "created_at": issue.created_at,
            "target_title": ref["title"],
            "target_admin_url": ref["admin_url"],
            "target_public_url": ref["public_url"],
        })
    return enriched


def _pending_tasks(
    limit_suggestions: int | None = 180,
    limit_issues: int | None = 120,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    pending_suggestions_qs = (
        SeoSuggestion.objects.select_related("content_type")
        .filter(status__in=[SeoSuggestion.Status.PENDING, SeoSuggestion.Status.NEEDS_CORRECTION])
        .order_by("-confidence", "-created_at")
    )
    if limit_suggestions is not None:
        pending_suggestions_qs = pending_suggestions_qs[:limit_suggestions]
    pending_suggestions = list(pending_suggestions_qs)

    open_issues_qs = (
        SeoIssue.objects.select_related("snapshot")
        .filter(status=SeoIssue.Status.OPEN)
        .order_by("-created_at")
    )
    if limit_issues is not None:
        open_issues_qs = open_issues_qs[:limit_issues]
    open_issues = list(open_issues_qs)

    tasks = [_suggestion_task_row(row) for row in pending_suggestions]
    tasks.extend(_issue_task_row(row) for row in open_issues)

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(
        key=lambda row: (
            priority_rank.get(row["priority"], 3),
            0 if row["task_kind"] == "suggestion" else 1,
            row["created_at"],
        ),
        reverse=False,
    )

    summary = {
        "total": len(tasks),
        "seo": sum(1 for row in tasks if row["domain"] == "seo"),
        "metadata": sum(1 for row in tasks if row["domain"] == "metadata"),
        "internal_linking": sum(1 for row in tasks if row["domain"] == "internal_linking"),
        "suggestions": sum(1 for row in tasks if row["task_kind"] == "suggestion"),
        "issues": sum(1 for row in tasks if row["task_kind"] == "issue"),
        "high": sum(1 for row in tasks if row["priority"] == "high"),
    }
    return tasks, summary


def _queue_counts_for_suggestions(
    *,
    suggestion_types: Sequence[str] | None = None,
    exclude_suggestion_types: Sequence[str] | None = None,
) -> dict[str, int]:
    queryset = SeoSuggestion.objects.all()
    if suggestion_types:
        queryset = queryset.filter(suggestion_type__in=suggestion_types)
    if exclude_suggestion_types:
        queryset = queryset.exclude(suggestion_type__in=exclude_suggestion_types)
    grouped = queryset.values("status").order_by().annotate(total=Count("id"))
    counts = {row["status"]: row["total"] for row in grouped}
    return {
        "pending": counts.get(SeoSuggestion.Status.PENDING, 0),
        "needs_correction": counts.get(SeoSuggestion.Status.NEEDS_CORRECTION, 0),
        "approved": counts.get(SeoSuggestion.Status.APPLIED, 0),
        "rejected": counts.get(SeoSuggestion.Status.REJECTED, 0),
    }


def _queue_counts_from_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "pending": 0,
        "needs_correction": 0,
        "approved": 0,
        "rejected": 0,
    }
    for row in rows:
        status = row.get("status")
        if status == SeoSuggestion.Status.PENDING:
            counts["pending"] += 1
        elif status == SeoSuggestion.Status.NEEDS_CORRECTION:
            counts["needs_correction"] += 1
        elif status == SeoSuggestion.Status.APPLIED:
            counts["approved"] += 1
        elif status == SeoSuggestion.Status.REJECTED:
            counts["rejected"] += 1
    return counts


def _paginate_rows(
    request: HttpRequest,
    rows: list[Any],
    *,
    param: str,
    page_size: int,
) -> tuple[Any, list[Any]]:
    paginator = Paginator(rows, page_size)
    page_obj = paginator.get_page(request.GET.get(param, 1))
    return page_obj, list(page_obj.object_list)


def _interlink_metrics() -> dict[str, Any]:
    post_ct = ContentType.objects.get_for_model(Post)
    page_ct = ContentType.objects.get_for_model(Page)
    node_keys: set[tuple[int, int]] = set()
    for post_id in Post.objects.values_list("id", flat=True):
        node_keys.add((post_ct.id, post_id))
    for page_id in Page.objects.values_list("id", flat=True):
        node_keys.add((page_ct.id, page_id))

    edges = list(
        SeoLinkEdge.objects.filter(status=SeoLinkEdge.Status.APPLIED).values_list(
            "source_content_type_id",
            "source_object_id",
            "target_content_type_id",
            "target_object_id",
        )
    )
    in_degree: dict[tuple[int, int], int] = {}
    out_degree: dict[tuple[int, int], int] = {}
    for source_ct, source_id, target_ct, target_id in edges:
        source_key = (source_ct, source_id)
        target_key = (target_ct, target_id)
        out_degree[source_key] = out_degree.get(source_key, 0) + 1
        in_degree[target_key] = in_degree.get(target_key, 0) + 1
    orphan_nodes = [key for key in node_keys if in_degree.get(key, 0) == 0]
    disconnected_nodes = [
        key for key in node_keys if in_degree.get(key, 0) == 0 and out_degree.get(key, 0) == 0
    ]
    total_nodes = len(node_keys)
    connected_nodes = total_nodes - len(disconnected_nodes)
    coverage_percent = round((connected_nodes / total_nodes) * 100, 2) if total_nodes else 0.0
    return {
        "total_nodes": total_nodes,
        "total_edges": len(edges),
        "orphan_nodes": len(orphan_nodes),
        "disconnected_nodes": len(disconnected_nodes),
        "coverage_percent": coverage_percent,
        "avg_in_degree": round(sum(in_degree.values()) / total_nodes, 3) if total_nodes else 0.0,
        "avg_out_degree": round(sum(out_degree.values()) / total_nodes, 3) if total_nodes else 0.0,
    }
