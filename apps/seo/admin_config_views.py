from __future__ import annotations

import json

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from blog.models import Post
from core.constants import ADMIN_PAGINATION_SIZE
from core.models import SeoSettings
from pages.models import Page

from .admin_config_forms import (
    SeoSuggestionEditForm,
    TaxonomySynonymGroupForm,
    TaxonomySynonymImportForm,
    TaxonomySynonymTermAddForm,
)
from .admin_config_services import (
    apply_suggestion_bulk,
    apply_suggestion_decision,
    auto_approve_safe_suggestions,
    cancel_scan_job,
    create_scan_job,
    edit_suggestion_payload,
    export_synonyms_payload,
    import_synonyms_payload,
    queue_snapshot,
    run_scan_job,
    scan_job_progress,
    seo_overview_with_queue,
    start_full_scan,
)
from .models import (
    SeoEngineSettings,
    SeoIssue,
    SeoLinkEdge,
    SeoScanJob,
    SeoSuggestion,
    SeoSuggestionRevision,
    TaxonomySynonymGroup,
    TaxonomySynonymTerm,
)

SEO_CONTROL_SECTIONS = {
    "scan",
    "results",
    "onsite",
    "redirects",
    "metadata",
    "interlinking",
    "settings",
    # Legacy alias; normalized to "onsite".
    "suggestions",
}
SEO_CONTROL_SECTION_ALIASES = {
    "suggestions": "onsite",
    "seo": "onsite",
    "redirect": "redirects",
}
ONSITE_TASKS_PAGE_SIZE = ADMIN_PAGINATION_SIZE
ONSITE_SUGGESTIONS_PAGE_SIZE = ADMIN_PAGINATION_SIZE


@staff_member_required
def legacy_action_center_redirect(request, *args, **kwargs):
    _ensure_admin_control_enabled()
    return _control_redirect("onsite")


def _ensure_admin_control_enabled():
    if not bool(getattr(settings, "ENABLE_ADMIN_CONTROL", True)):
        raise Http404("SEO Control is disabled.")


def _admin_control_context(
    *,
    section: str,
    title: str,
    subtitle: str = "",
    breadcrumb_parent_label: str = "",
    breadcrumb_parent_url: str = "",
):
    return {
        "admin_control_enabled": True,
        "admin_control_section": section,
        "admin_control_title": title,
        "admin_control_subtitle": subtitle,
        "admin_control_breadcrumb_parent_label": breadcrumb_parent_label,
        "admin_control_breadcrumb_parent_url": breadcrumb_parent_url,
        "title": title,
    }


def _normalize_control_section(section: str | None, default: str = "scan"):
    safe = (section or "").strip().lower()
    safe = SEO_CONTROL_SECTION_ALIASES.get(safe, safe)
    return safe if safe in SEO_CONTROL_SECTIONS else default


def _control_url(section: str = "scan", **params):
    safe_section = _normalize_control_section(section)
    base = reverse("admin_config:seo_control_canonical_section", kwargs={"section": safe_section})
    query_parts = []
    for key, value in params.items():
        if value not in {None, ""}:
            query_parts.append(f"{key}={value}")
    suffix = f"?{'&'.join(query_parts)}" if query_parts else ""
    return f"{base}{suffix}"


def _control_redirect(section: str = "scan", **params):
    return redirect(_control_url(section=section, **params))


def _query_without_keys(request, *keys: str) -> str:
    query = request.GET.copy()
    for key in keys:
        query.pop(key, None)
    return query.urlencode()


def _resolve_return_section(request, default: str = "onsite"):
    raw = (
        request.POST.get("return_section")
        or request.GET.get("return_section")
        or request.GET.get("section")
    )
    return _normalize_control_section(raw, default=default)


def _suggestion_target(suggestion: SeoSuggestion):
    model = suggestion.content_type.model_class()
    if not model:
        return {"title": "Unknown", "public_url": "", "admin_url": ""}
    target = model.objects.filter(pk=suggestion.object_id).first()
    if not target:
        return {"title": "Deleted content", "public_url": "", "admin_url": ""}
    title = getattr(target, "title", "") or str(target)
    public_url = ""
    admin_url = ""
    try:
        public_url = target.get_absolute_url()
    except Exception:
        public_url = ""
    try:
        admin_url = reverse(
            f"admin:{target._meta.app_label}_{target._meta.model_name}_change",
            args=[target.pk],
        )
    except Exception:
        admin_url = ""
    return {"title": title, "public_url": public_url, "admin_url": admin_url}


def _suggestion_rows(
    *,
    statuses=None,
    suggestion_types=None,
    exclude_suggestion_types=None,
    limit=250,
):
    queryset = SeoSuggestion.objects.select_related("content_type").order_by("-created_at")
    if statuses:
        queryset = queryset.filter(status__in=statuses)
    if suggestion_types:
        queryset = queryset.filter(suggestion_type__in=suggestion_types)
    if exclude_suggestion_types:
        queryset = queryset.exclude(suggestion_type__in=exclude_suggestion_types)
    rows = []
    if limit is None:
        iterator = queryset
    else:
        iterator = queryset[:limit]
    for suggestion in iterator:
        target = _suggestion_target(suggestion)
        rows.append(
            {
                "id": suggestion.id,
                "status": suggestion.status,
                "type": suggestion.suggestion_type,
                "confidence": suggestion.confidence,
                "created_at": suggestion.created_at,
                "payload_json": suggestion.payload_json,
                "target_title": target["title"],
                "target_public_url": target["public_url"],
                "target_admin_url": target["admin_url"],
                "object_id": suggestion.object_id,
                "content_type_id": suggestion.content_type_id,
                "content_model": suggestion.content_type.model,
            }
        )
    return rows


def _suggestion_task_row(suggestion: SeoSuggestion):
    target = _suggestion_target(suggestion)
    payload = suggestion.payload_json or {}
    suggestion_type = suggestion.suggestion_type
    if suggestion_type == SeoSuggestion.SuggestionType.METADATA:
        domain = "metadata"
    elif suggestion_type == SeoSuggestion.SuggestionType.INTERLINK:
        domain = "internal_linking"
    else:
        domain = "seo"
    priority = "high" if suggestion.confidence >= 0.85 else "medium" if suggestion.confidence >= 0.6 else "low"

    if suggestion_type == SeoSuggestion.SuggestionType.METADATA:
        title = "Metadata enhancement"
        description = "Update meta title/description/canonical values for stronger SERP presentation."
        recommendation = (
            "Validate metadata intent alignment. Approve if title/description are accurate and non-duplicative."
        )
        evidence = (
            f"title={payload.get('meta_title', '')[:70]} | "
            f"description={payload.get('meta_description', '')[:120]}"
        )
    elif suggestion_type == SeoSuggestion.SuggestionType.INTERLINK:
        anchor = (payload.get("anchor_text") or "").strip()
        target_url = (payload.get("target_url") or "").strip()
        description = (
            f"Insert internal link from anchor '{anchor or 'N/A'}' to '{target_url or 'N/A'}'."
        )
        title = "Internal link insertion"
        recommendation = (
            "Approve only if anchor appears naturally in body text and target destination is contextually relevant."
        )
        evidence = f"score={float(payload.get('score', 0.0)):.3f} | target={target_url or 'N/A'}"
    else:
        old_path = (payload.get("old_path") or "").strip()
        target_url = (payload.get("suggested_target") or "").strip()
        status_code = payload.get("status_code", 301)
        title = "Redirect rule"
        description = f"Add redirect for '{old_path or 'N/A'}' to '{target_url or '/'}'."
        recommendation = (
            "Approve to preserve crawl continuity and prevent broken-path indexing where redirect is valid."
        )
        evidence = f"status_code={status_code}"

    return {
        "task_kind": "suggestion",
        "task_ref": f"S-{suggestion.id}",
        "id": suggestion.id,
        "domain": domain,
        "priority": priority,
        "status": suggestion.status,
        "type_label": suggestion.get_suggestion_type_display(),
        "title": title,
        "description": description,
        "recommendation": recommendation,
        "evidence": evidence,
        "confidence": suggestion.confidence,
        "created_at": suggestion.created_at,
        "target_title": target["title"],
        "target_admin_url": target["admin_url"],
        "target_public_url": target["public_url"],
        "target_content_type_id": suggestion.content_type_id,
        "target_object_id": suggestion.object_id,
        "suggestion_id": suggestion.id,
    }


def _issue_domain(check_key: str):
    lower_key = (check_key or "").strip().lower()
    if any(token in lower_key for token in {"internal", "link", "anchor", "orphan"}):
        return "internal_linking"
    return "seo"


def _open_issue_target_refs(*, domain: str | None = None):
    refs = set()
    queryset = (
        SeoIssue.objects.select_related("snapshot")
        .filter(status=SeoIssue.Status.OPEN)
        .order_by("-created_at")
    )
    for issue in queryset:
        issue_domain = _issue_domain(issue.check_key)
        if domain and issue_domain != domain:
            continue
        refs.add((issue.snapshot.content_type_id, issue.snapshot.object_id))
    return refs


def _issue_task_row(issue: SeoIssue):
    check_key = (issue.check_key or "").strip()
    domain = _issue_domain(check_key)
    severity = (issue.severity or "").lower()
    priority = "high" if severity == SeoIssue.Severity.CRITICAL else "medium"
    suggestion_text = (issue.suggested_fix or "").strip() or "Review content and apply a manual fix, then rescan."
    evidence_url = getattr(issue.snapshot, "url", "") or ""

    return {
        "task_kind": "issue",
        "task_ref": f"I-{issue.id}",
        "id": issue.id,
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
        "target_title": evidence_url or "Content snapshot",
        "target_admin_url": "",
        "target_public_url": evidence_url,
        "target_content_type_id": issue.snapshot.content_type_id,
        "target_object_id": issue.snapshot.object_id,
        "suggestion_id": None,
    }


def _resolve_content_ref(cache: dict, content_type, object_id: int):
    if not content_type:
        return {"title": "Unknown", "admin_url": "", "public_url": ""}
    cache_key = (content_type.id, int(object_id))
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
    try:
        admin_url = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
            args=[obj.pk],
        )
    except Exception:
        admin_url = ""
    try:
        public_url = obj.get_absolute_url()
    except Exception:
        public_url = ""
    cache[cache_key] = {
        "title": title,
        "admin_url": admin_url,
        "public_url": public_url,
    }
    return cache[cache_key]


def _interlink_edge_rows(limit: int = 220):
    rows = []
    ref_cache = {}
    queryset = (
        SeoLinkEdge.objects.select_related("source_content_type", "target_content_type")
        .order_by("-created_at")[:limit]
    )
    for edge in queryset:
        source = _resolve_content_ref(ref_cache, edge.source_content_type, edge.source_object_id)
        target = _resolve_content_ref(ref_cache, edge.target_content_type, edge.target_object_id)
        rows.append(
            {
                "id": edge.id,
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


def _interlink_suggestion_rows(limit: int = 220):
    rows = []
    ref_cache = {}
    queryset = (
        SeoSuggestion.objects.select_related("content_type")
        .filter(
            suggestion_type=SeoSuggestion.SuggestionType.INTERLINK,
            status__in=[SeoSuggestion.Status.PENDING, SeoSuggestion.Status.NEEDS_CORRECTION],
        )
        .order_by("-confidence", "-created_at")[:limit]
    )
    for suggestion in queryset:
        payload = suggestion.payload_json or {}
        source = _resolve_content_ref(ref_cache, suggestion.content_type, suggestion.object_id)
        target_title = payload.get("target_title", "") or payload.get("target_url", "") or "Target"
        target_admin_url = ""
        target_public_url = payload.get("target_url", "")
        target_type = (payload.get("target_type") or "").strip()
        target_id = payload.get("target_id")
        if target_type in {"post", "page"} and str(target_id or "").isdigit():
            target_model = Post if target_type == "post" else Page
            target_ct = ContentType.objects.get_for_model(target_model)
            target = _resolve_content_ref(ref_cache, target_ct, int(target_id))
            target_title = target["title"]
            target_admin_url = target["admin_url"]
            target_public_url = target["public_url"] or target_public_url
        rows.append(
            {
                "id": suggestion.id,
                "status": suggestion.status,
                "confidence": suggestion.confidence,
                "created_at": suggestion.created_at,
                "anchor_text": payload.get("anchor_text", ""),
                "score": float(payload.get("score", 0.0)),
                "source_title": source["title"],
                "source_admin_url": source["admin_url"],
                "source_public_url": source["public_url"],
                "target_title": target_title,
                "target_admin_url": target_admin_url,
                "target_public_url": target_public_url,
            }
        )
    return rows


def _seo_issue_rows(limit: int = 220):
    rows = []
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


def _pending_tasks(limit_suggestions: int | None = 180, limit_issues: int | None = 120):
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


def _queue_counts_for_suggestions(*, suggestion_types=None, exclude_suggestion_types=None):
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


def _queue_counts_from_rows(rows):
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


def _paginate_rows(request, rows, *, param: str, page_size: int):
    paginator = Paginator(rows, page_size)
    page_obj = paginator.get_page(request.GET.get(param, 1))
    return page_obj, list(page_obj.object_list)


def _interlink_metrics():
    post_ct = ContentType.objects.get_for_model(Post)
    page_ct = ContentType.objects.get_for_model(Page)
    node_keys = set()
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
    in_degree = {}
    out_degree = {}
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


def _control_common_context(request):
    job_id = (request.GET.get("job_id") or "").strip()
    selected_job = None
    if job_id.isdigit():
        selected_job = SeoScanJob.objects.filter(pk=int(job_id)).first()

    settings_obj = SeoEngineSettings.get_solo()
    defaults_obj = SeoSettings.get_solo()
    all_jobs_qs = SeoScanJob.objects.order_by("-created_at")
    scan_jobs_qs = all_jobs_qs.exclude(job_type=SeoScanJob.JobType.INTERLINKS)
    scan_jobs = scan_jobs_qs[:50]
    selected_scan_job = (
        selected_job
        if selected_job and selected_job.job_type != SeoScanJob.JobType.INTERLINKS
        else scan_jobs_qs.first()
    )
    interlink_jobs_qs = all_jobs_qs.filter(job_type=SeoScanJob.JobType.INTERLINKS)
    interlink_jobs = interlink_jobs_qs[:50]
    selected_interlink_job = (
        selected_job
        if selected_job and selected_job.job_type == SeoScanJob.JobType.INTERLINKS
        else interlink_jobs_qs.first()
    )
    pending_task_rows, pending_task_summary = _pending_tasks(limit_suggestions=None, limit_issues=None)
    pending_interlink_tasks = [row for row in pending_task_rows if row["domain"] == "internal_linking"][:160]
    pending_metadata_tasks = [row for row in pending_task_rows if row["domain"] == "metadata"][:160]
    onsite_excluded_types = [
        SeoSuggestion.SuggestionType.METADATA,
        SeoSuggestion.SuggestionType.INTERLINK,
    ]
    metadata_types = [SeoSuggestion.SuggestionType.METADATA]
    interlink_types = [SeoSuggestion.SuggestionType.INTERLINK]
    redirect_types = [SeoSuggestion.SuggestionType.REDIRECT]
    open_seo_issue_targets = _open_issue_target_refs(domain="seo")
    pending_seo_tasks_all = [
        row
        for row in pending_task_rows
        if row["domain"] == "seo"
        and (row.get("target_content_type_id"), row.get("target_object_id")) in open_seo_issue_targets
    ]
    pending_seo_task_page_obj, pending_seo_task_rows = _paginate_rows(
        request,
        pending_seo_tasks_all,
        param="onsite_page",
        page_size=ONSITE_TASKS_PAGE_SIZE,
    )
    onsite_suggestion_rows_all = [
        row
        for row in _suggestion_rows(
            exclude_suggestion_types=onsite_excluded_types,
            limit=None,
        )
        if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
    ]
    onsite_suggestion_page_obj, onsite_suggestion_rows = _paginate_rows(
        request,
        onsite_suggestion_rows_all,
        param="onsite_suggestion_page",
        page_size=ONSITE_SUGGESTIONS_PAGE_SIZE,
    )
    redirect_suggestion_rows_all = [
        row
        for row in _suggestion_rows(
            suggestion_types=redirect_types,
            limit=None,
        )
        if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
    ]
    redirect_suggestion_page_obj, redirect_suggestion_rows = _paginate_rows(
        request,
        redirect_suggestion_rows_all,
        param="redirect_page",
        page_size=ONSITE_SUGGESTIONS_PAGE_SIZE,
    )
    pending_redirect_tasks_all = [
        row
        for row in pending_task_rows
        if row["domain"] == "seo"
        and row["task_kind"] == "suggestion"
        and (row.get("target_content_type_id"), row.get("target_object_id")) in open_seo_issue_targets
    ]
    pending_redirect_task_page_obj, pending_redirect_task_rows = _paginate_rows(
        request,
        pending_redirect_tasks_all,
        param="redirect_task_page",
        page_size=ONSITE_TASKS_PAGE_SIZE,
    )
    pending_seo_task_summary = {
        "total": len(pending_seo_tasks_all),
        "high": sum(1 for row in pending_seo_tasks_all if row["priority"] == "high"),
    }
    pending_redirect_task_summary = {
        "total": len(pending_redirect_tasks_all),
        "high": sum(1 for row in pending_redirect_tasks_all if row["priority"] == "high"),
    }
    return {
        "seo_overview": seo_overview_with_queue(),
        "queue_counts": queue_snapshot(),
        "onsite_queue_counts": _queue_counts_from_rows(onsite_suggestion_rows_all),
        "redirect_queue_counts": _queue_counts_from_rows(redirect_suggestion_rows_all),
        "metadata_queue_counts": _queue_counts_for_suggestions(
            suggestion_types=metadata_types,
        ),
        "interlink_queue_counts": _queue_counts_for_suggestions(
            suggestion_types=interlink_types,
        ),
        "interlink_metrics": _interlink_metrics(),
        "latest_issues": SeoIssue.objects.filter(status=SeoIssue.Status.OPEN).order_by("-created_at")[:40],
        "jobs": scan_jobs,
        "scan_jobs": scan_jobs,
        "interlink_jobs": interlink_jobs,
        "job_types": [
            (value, label)
            for value, label in SeoScanJob.JobType.choices
            if value != SeoScanJob.JobType.INTERLINKS
        ],
        "latest_job": all_jobs_qs.first(),
        "selected_job": selected_job,
        "selected_job_progress": scan_job_progress(selected_job) if selected_job else None,
        "selected_scan_job": selected_scan_job,
        "selected_scan_job_progress": (
            scan_job_progress(selected_scan_job) if selected_scan_job else None
        ),
        "selected_scan_items": (
            selected_scan_job.items.select_related("content_type").order_by("-id")[:180]
            if selected_scan_job
            else []
        ),
        "selected_interlink_job": selected_interlink_job,
        "selected_interlink_job_progress": (
            scan_job_progress(selected_interlink_job) if selected_interlink_job else None
        ),
        "selected_interlink_items": (
            selected_interlink_job.items.select_related("content_type").order_by("-id")[:180]
            if selected_interlink_job
            else []
        ),
        "pending_task_rows": pending_task_rows[:220],
        "pending_task_summary": pending_task_summary,
        "pending_interlink_task_rows": pending_interlink_tasks,
        "pending_seo_task_rows": pending_seo_task_rows,
        "pending_seo_task_page_obj": pending_seo_task_page_obj,
        "pending_seo_task_summary": pending_seo_task_summary,
        "pending_redirect_task_rows": pending_redirect_task_rows,
        "pending_redirect_task_page_obj": pending_redirect_task_page_obj,
        "pending_redirect_task_summary": pending_redirect_task_summary,
        "pending_metadata_task_rows": pending_metadata_tasks,
        "seo_issue_rows": _seo_issue_rows(),
        "interlink_edge_rows": _interlink_edge_rows(),
        "interlink_suggestion_rows": _interlink_suggestion_rows(),
        "onsite_suggestion_rows": onsite_suggestion_rows,
        "onsite_suggestion_page_obj": onsite_suggestion_page_obj,
        "redirect_suggestion_rows": redirect_suggestion_rows,
        "redirect_suggestion_page_obj": redirect_suggestion_page_obj,
        "control_querystring": request.GET.urlencode(),
        "onsite_page_query": _query_without_keys(request, "onsite_page"),
        "onsite_suggestion_page_query": _query_without_keys(request, "onsite_suggestion_page"),
        "redirect_task_page_query": _query_without_keys(request, "redirect_task_page"),
        "redirect_page_query": _query_without_keys(request, "redirect_page"),
        "onsite_lane_rows": {
            "pending": [
                row
                for row in _suggestion_rows(
                    statuses=[SeoSuggestion.Status.PENDING],
                    exclude_suggestion_types=onsite_excluded_types,
                    limit=None,
                )
                if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
            ][:120],
            "needs_correction": [
                row
                for row in _suggestion_rows(
                    statuses=[SeoSuggestion.Status.NEEDS_CORRECTION],
                    exclude_suggestion_types=onsite_excluded_types,
                    limit=None,
                )
                if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
            ][:120],
            "approved": [
                row
                for row in _suggestion_rows(
                    statuses=[SeoSuggestion.Status.APPLIED],
                    exclude_suggestion_types=onsite_excluded_types,
                    limit=None,
                )
                if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
            ][:120],
            "rejected": [
                row
                for row in _suggestion_rows(
                    statuses=[SeoSuggestion.Status.REJECTED],
                    exclude_suggestion_types=onsite_excluded_types,
                    limit=None,
                )
                if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
            ][:120],
        },
        "redirect_lane_rows": {
            "pending": [
                row
                for row in _suggestion_rows(
                    statuses=[SeoSuggestion.Status.PENDING],
                    suggestion_types=redirect_types,
                    limit=None,
                )
                if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
            ][:120],
            "needs_correction": [
                row
                for row in _suggestion_rows(
                    statuses=[SeoSuggestion.Status.NEEDS_CORRECTION],
                    suggestion_types=redirect_types,
                    limit=None,
                )
                if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
            ][:120],
            "approved": [
                row
                for row in _suggestion_rows(
                    statuses=[SeoSuggestion.Status.APPLIED],
                    suggestion_types=redirect_types,
                    limit=None,
                )
                if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
            ][:120],
            "rejected": [
                row
                for row in _suggestion_rows(
                    statuses=[SeoSuggestion.Status.REJECTED],
                    suggestion_types=redirect_types,
                    limit=None,
                )
                if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
            ][:120],
        },
        "metadata_suggestion_rows": _suggestion_rows(
            suggestion_types=metadata_types,
            limit=300,
        ),
        "metadata_lane_rows": {
            "pending": _suggestion_rows(
                statuses=[SeoSuggestion.Status.PENDING],
                suggestion_types=metadata_types,
                limit=120,
            ),
            "needs_correction": _suggestion_rows(
                statuses=[SeoSuggestion.Status.NEEDS_CORRECTION],
                suggestion_types=metadata_types,
                limit=120,
            ),
            "approved": _suggestion_rows(
                statuses=[SeoSuggestion.Status.APPLIED],
                suggestion_types=metadata_types,
                limit=120,
            ),
            "rejected": _suggestion_rows(
                statuses=[SeoSuggestion.Status.REJECTED],
                suggestion_types=metadata_types,
                limit=120,
            ),
        },
        "metadata_template_injection": {
            "canonical": bool(defaults_obj.canonical_base_url.strip()),
            "open_graph": bool(defaults_obj.enable_open_graph),
            "twitter_cards": bool(defaults_obj.enable_twitter_cards),
            "organization_schema": bool(defaults_obj.organization_schema_name.strip()),
        },
        "engine_settings": settings_obj,
        "seo_defaults": defaults_obj,
        "synonym_groups": TaxonomySynonymGroup.objects.prefetch_related("terms").order_by(
            "scope",
            "name",
        )[:40],
    }


@staff_member_required
@require_GET
def seo_overview(request):
    _ensure_admin_control_enabled()
    context = _admin_control_context(
        section="seo_overview",
        title="SEO Overview",
        subtitle="Global SEO health, issue trends, and queue pressure.",
    )
    context.update(_control_common_context(request))
    return render(request, "seo/admin/overview.html", context)


@staff_member_required
@require_GET
def seo_control_center(request, section: str | None = None):
    _ensure_admin_control_enabled()
    active_section = _normalize_control_section(section or request.GET.get("section") or "scan")
    context = _admin_control_context(
        section="seo_control",
        title="SEO Control",
        subtitle=(
            "Centralized scan, results, on-site SEO, redirects, interlinking, "
            "metadata, and settings."
        ),
    )
    context.update(_control_common_context(request))
    context["active_section"] = active_section
    return render(request, "seo/admin/control.html", context)


@staff_member_required
@require_POST
def seo_control_run(request):
    _ensure_admin_control_enabled()
    notes = (request.POST.get("notes") or "").strip()
    job = start_full_scan(started_by=request.user, notes=notes, run_immediately=True)
    if job.status == SeoScanJob.Status.COMPLETED:
        messages.success(
            request,
            (
                f"Automation scan completed (job #{job.id}): "
                f"{job.processed_items}/{job.total_items} processed, "
                f"{job.warning_count} warnings, {job.error_count} errors."
            ),
        )
    else:
        messages.warning(
            request,
            (
                f"Automation scan finished with status '{job.status}' (job #{job.id}): "
                f"{job.processed_items}/{job.total_items} processed."
            ),
        )
    return _control_redirect("scan", job_id=job.id)


@staff_member_required
@require_POST
def seo_control_autopilot(request):
    _ensure_admin_control_enabled()
    try:
        min_confidence = float(
            request.POST.get(
                "min_confidence",
                str(SeoEngineSettings.get_solo().autopilot_min_confidence),
            )
        )
    except ValueError:
        min_confidence = SeoEngineSettings.get_solo().autopilot_min_confidence
    try:
        limit = int(request.POST.get("limit", "200"))
    except ValueError:
        limit = 200
    result = auto_approve_safe_suggestions(
        reviewer=request.user,
        min_confidence=max(min(min_confidence, 1.0), 0.0),
        limit=max(min(limit, 1000), 1),
    )
    messages.success(
        request,
        (
            f"Autopilot approved {result['approved']} suggestions at threshold "
            f"{result['threshold']:.2f}. {result['skipped']} skipped."
        ),
    )
    return _control_redirect("metadata")


@staff_member_required
@require_GET
def seo_control_section(request, section: str):
    _ensure_admin_control_enabled()
    safe_section = _normalize_control_section(section, default="")
    if not safe_section:
        raise Http404("Unknown SEO section.")
    context = _control_common_context(request)
    context["active_section"] = safe_section
    template_map = {
        "scan": "seo/admin/partials/seo_control_scan.html",
        "results": "seo/admin/partials/seo_control_results.html",
        "onsite": "seo/admin/partials/seo_control_suggestions.html",
        "redirects": "seo/admin/partials/seo_control_redirects.html",
        "metadata": "seo/admin/partials/seo_control_metadata.html",
        "interlinking": "seo/admin/partials/seo_control_interlinking.html",
        "settings": "seo/admin/partials/seo_control_settings.html",
    }
    return render(request, template_map[safe_section], context)


@staff_member_required
@require_POST
def seo_control_settings_save(request):
    _ensure_admin_control_enabled()
    engine = SeoEngineSettings.get_solo()
    defaults_obj = SeoSettings.get_solo()
    fields = []
    seo_fields = []

    def parse_checkbox(name: str, current: bool):
        if name not in request.POST:
            return current
        return request.POST.get(name) == "on"

    if "autopilot_min_confidence" in request.POST:
        try:
            engine.autopilot_min_confidence = max(
                min(float(request.POST.get("autopilot_min_confidence", "0.82")), 1.0),
                0.0,
            )
            fields.append("autopilot_min_confidence")
        except ValueError:
            pass
    if "link_suggestion_min_score" in request.POST:
        try:
            engine.link_suggestion_min_score = max(
                min(float(request.POST.get("link_suggestion_min_score", "0.45")), 1.0),
                0.0,
            )
            fields.append("link_suggestion_min_score")
        except ValueError:
            pass
    if "min_links_per_doc" in request.POST:
        try:
            engine.min_links_per_doc = max(int(request.POST.get("min_links_per_doc", "3")), 1)
            fields.append("min_links_per_doc")
        except ValueError:
            pass
    if "whitehat_cap_max_links" in request.POST:
        try:
            engine.whitehat_cap_max_links = max(
                int(request.POST.get("whitehat_cap_max_links", "8")),
                engine.min_links_per_doc,
            )
            fields.append("whitehat_cap_max_links")
        except ValueError:
            pass
    if "canonical_query_allowlist" in request.POST:
        engine.canonical_query_allowlist = (request.POST.get("canonical_query_allowlist") or "").strip()
        fields.append("canonical_query_allowlist")
    if "enable_checks" in request.POST:
        engine.enable_checks = parse_checkbox("enable_checks", engine.enable_checks)
        fields.append("enable_checks")
    if "enable_live_checks" in request.POST:
        engine.enable_live_checks = parse_checkbox("enable_live_checks", engine.enable_live_checks)
        fields.append("enable_live_checks")
    if "auto_fix_enabled" in request.POST:
        engine.auto_fix_enabled = parse_checkbox("auto_fix_enabled", engine.auto_fix_enabled)
        fields.append("auto_fix_enabled")
    if "auto_update_published_links" in request.POST:
        engine.auto_update_published_links = parse_checkbox(
            "auto_update_published_links",
            engine.auto_update_published_links,
        )
        fields.append("auto_update_published_links")
    if "noindex_paginated_filters" in request.POST:
        engine.noindex_paginated_filters = parse_checkbox(
            "noindex_paginated_filters",
            engine.noindex_paginated_filters,
        )
        fields.append("noindex_paginated_filters")
    if "apply_interlinks_on_audit" in request.POST:
        engine.apply_interlinks_on_audit = parse_checkbox(
            "apply_interlinks_on_audit",
            engine.apply_interlinks_on_audit,
        )
        fields.append("apply_interlinks_on_audit")

    if "default_meta_title" in request.POST:
        defaults_obj.default_meta_title = (
            request.POST.get("default_meta_title", defaults_obj.default_meta_title) or ""
        ).strip()
        seo_fields.append("default_meta_title")
    if "default_meta_description" in request.POST:
        defaults_obj.default_meta_description = (
            request.POST.get("default_meta_description", defaults_obj.default_meta_description)
            or ""
        ).strip()
        seo_fields.append("default_meta_description")
    if "canonical_base_url" in request.POST:
        defaults_obj.canonical_base_url = (
            request.POST.get("canonical_base_url", defaults_obj.canonical_base_url) or ""
        ).strip()
        seo_fields.append("canonical_base_url")
    if "default_og_image_url" in request.POST:
        defaults_obj.default_og_image_url = (
            request.POST.get("default_og_image_url", defaults_obj.default_og_image_url) or ""
        ).strip()
        seo_fields.append("default_og_image_url")
    if "twitter_site_handle" in request.POST:
        defaults_obj.twitter_site_handle = (
            request.POST.get("twitter_site_handle", defaults_obj.twitter_site_handle) or ""
        ).strip()
        seo_fields.append("twitter_site_handle")
    if "organization_schema_name" in request.POST:
        defaults_obj.organization_schema_name = (
            request.POST.get("organization_schema_name", defaults_obj.organization_schema_name)
            or ""
        ).strip()
        seo_fields.append("organization_schema_name")
    if "organization_schema_url" in request.POST:
        defaults_obj.organization_schema_url = (
            request.POST.get("organization_schema_url", defaults_obj.organization_schema_url)
            or ""
        ).strip()
        seo_fields.append("organization_schema_url")
    if "google_site_verification" in request.POST:
        defaults_obj.google_site_verification = (
            request.POST.get("google_site_verification", defaults_obj.google_site_verification)
            or ""
        ).strip()
        seo_fields.append("google_site_verification")
    if "bing_site_verification" in request.POST:
        defaults_obj.bing_site_verification = (
            request.POST.get("bing_site_verification", defaults_obj.bing_site_verification)
            or ""
        ).strip()
        seo_fields.append("bing_site_verification")
    if "yandex_site_verification" in request.POST:
        defaults_obj.yandex_site_verification = (
            request.POST.get("yandex_site_verification", defaults_obj.yandex_site_verification)
            or ""
        ).strip()
        seo_fields.append("yandex_site_verification")
    if "pinterest_site_verification" in request.POST:
        defaults_obj.pinterest_site_verification = (
            request.POST.get("pinterest_site_verification", defaults_obj.pinterest_site_verification)
            or ""
        ).strip()
        seo_fields.append("pinterest_site_verification")
    if "robots_index" in request.POST:
        defaults_obj.robots_index = parse_checkbox("robots_index", defaults_obj.robots_index)
        seo_fields.append("robots_index")
    if "robots_follow" in request.POST:
        defaults_obj.robots_follow = parse_checkbox("robots_follow", defaults_obj.robots_follow)
        seo_fields.append("robots_follow")
    if "enable_open_graph" in request.POST:
        defaults_obj.enable_open_graph = parse_checkbox(
            "enable_open_graph",
            defaults_obj.enable_open_graph,
        )
        seo_fields.append("enable_open_graph")
    if "enable_twitter_cards" in request.POST:
        defaults_obj.enable_twitter_cards = parse_checkbox(
            "enable_twitter_cards",
            defaults_obj.enable_twitter_cards,
        )
        seo_fields.append("enable_twitter_cards")

    if fields:
        engine.save(update_fields=[*set(fields), "updated_at"])
    if seo_fields:
        defaults_obj.save(update_fields=[*set(seo_fields), "updated_at"])

    if fields or seo_fields:
        messages.success(request, "SEO settings updated.")
    else:
        messages.warning(request, "No valid settings changes detected.")
    return _control_redirect("settings")


@staff_member_required
@require_GET
def seo_control_job_progress(request, job_id: int):
    _ensure_admin_control_enabled()
    job = get_object_or_404(SeoScanJob, pk=job_id)
    return JsonResponse(scan_job_progress(job))


@staff_member_required
@require_POST
def seo_control_suggestion_action(request, suggestion_id: int, action: str):
    _ensure_admin_control_enabled()
    return_section = _resolve_return_section(request, default="onsite")
    result = apply_suggestion_decision(
        suggestion_id=suggestion_id,
        action=action,
        reviewer=request.user,
    )
    level = messages.SUCCESS if result.get("ok") else messages.WARNING
    messages.add_message(request, level, result.get("message", "Action completed."))
    return _control_redirect(return_section)


@staff_member_required
def seo_control_suggestion_edit(request, suggestion_id: int):
    _ensure_admin_control_enabled()
    return_section = _resolve_return_section(request, default="onsite")
    suggestion = get_object_or_404(SeoSuggestion, pk=suggestion_id)
    form = SeoSuggestionEditForm(request.POST or None, suggestion=suggestion)
    if request.method == "POST" and form.is_valid():
        suggestion = edit_suggestion_payload(
            suggestion=suggestion,
            payload=form.cleaned_data["payload_json"],
            edited_by=request.user,
            note=form.cleaned_data.get("note", ""),
        )
        apply_after_save = (request.POST.get("apply_action") or "").strip()
        if apply_after_save in {"approve", "reject"}:
            apply_suggestion_decision(
                suggestion_id=suggestion.id,
                action=apply_after_save,
                reviewer=request.user,
            )
        messages.success(request, "Suggestion payload updated.")
        return _control_redirect(return_section)
    context = _admin_control_context(
        section="seo_control",
        title=f"Edit Suggestion #{suggestion.id}",
        subtitle="Review and modify payload before decision.",
        breadcrumb_parent_label="SEO Control",
        breadcrumb_parent_url=_control_url(return_section),
    )
    context.update(
        {
            "form": form,
            "suggestion": suggestion,
            "revisions": SeoSuggestionRevision.objects.filter(suggestion=suggestion).order_by("-edited_at")[:20],
            "return_section": return_section,
        }
    )
    return render(request, "seo/admin/queue_edit.html", context)


@staff_member_required
@require_POST
def seo_control_suggestion_bulk(request):
    _ensure_admin_control_enabled()
    return_section = _resolve_return_section(request, default="onsite")
    action = (request.POST.get("bulk_action") or "").strip()
    selected_ids = request.POST.getlist("selected_suggestions")
    if action == "reject" and not request.user.is_superuser:
        messages.error(request, "Superuser permission required for bulk reject.")
        return _control_redirect(return_section)
    if action not in {"approve", "reject"}:
        messages.error(request, "Unknown bulk action.")
        return _control_redirect(return_section)
    result = apply_suggestion_bulk(action=action, ids=selected_ids, reviewer=request.user)
    messages.success(
        request,
        f"{result['success']} suggestions processed. {result['skipped']} skipped.",
    )
    return _control_redirect(return_section)


@staff_member_required
def seo_engine(request):
    _ensure_admin_control_enabled()
    return _control_redirect("settings")


@staff_member_required
@require_GET
def seo_scan(request):
    _ensure_admin_control_enabled()
    return _control_redirect("scan", job_id=request.GET.get("job_id", ""))


@staff_member_required
@require_POST
def seo_scan_start(request):
    _ensure_admin_control_enabled()
    raw_job_type = (request.POST.get("job_type") or SeoScanJob.JobType.FULL).strip()
    if raw_job_type == SeoScanJob.JobType.INTERLINKS:
        return seo_interlink_scan_start(request)
    job_type = raw_job_type if raw_job_type in SeoScanJob.JobType.values else SeoScanJob.JobType.FULL
    notes = (request.POST.get("notes") or "").strip()
    job = create_scan_job(job_type=job_type, started_by=request.user, notes=notes)
    result = run_scan_job(job.id)
    job.refresh_from_db()
    if request.htmx:
        return JsonResponse(
            {
                "ok": bool(result.get("ok", False)),
                "job_id": job.id,
                "status": job.status,
                "processed_items": job.processed_items,
                "total_items": job.total_items,
                "warning_count": job.warning_count,
                "error_count": job.error_count,
                "redirect": _control_url("scan", job_id=job.id),
            }
        )
    if job.status == SeoScanJob.Status.COMPLETED:
        messages.success(
            request,
            (
                f"Scan completed (job #{job.id}): {job.processed_items}/{job.total_items} "
                f"processed, {job.warning_count} warnings, {job.error_count} errors."
            ),
        )
    else:
        messages.warning(
            request,
            (
                f"Scan ended with status '{job.status}' (job #{job.id}): "
                f"{job.processed_items}/{job.total_items} processed."
            ),
        )
    return _control_redirect("scan", job_id=job.id)


@staff_member_required
@require_POST
def seo_interlink_scan_start(request):
    _ensure_admin_control_enabled()
    notes = (request.POST.get("notes") or "").strip()
    job = create_scan_job(
        job_type=SeoScanJob.JobType.INTERLINKS,
        started_by=request.user,
        notes=notes or "Manual internal linking scan.",
    )
    result = run_scan_job(job.id)
    job.refresh_from_db()
    if request.htmx:
        return JsonResponse(
            {
                "ok": bool(result.get("ok", False)),
                "job_id": job.id,
                "status": job.status,
                "processed_items": job.processed_items,
                "total_items": job.total_items,
                "warning_count": job.warning_count,
                "error_count": job.error_count,
                "redirect": _control_url("interlinking", job_id=job.id),
            }
        )
    if job.status == SeoScanJob.Status.COMPLETED:
        messages.success(
            request,
            (
                f"Internal linking scan completed (job #{job.id}): "
                f"{job.processed_items}/{job.total_items} processed, "
                f"{job.warning_count} warnings, {job.error_count} errors."
            ),
        )
    else:
        messages.warning(
            request,
            (
                f"Internal linking scan ended with status '{job.status}' (job #{job.id}): "
                f"{job.processed_items}/{job.total_items} processed."
            ),
        )
    return _control_redirect("interlinking", job_id=job.id)


@staff_member_required
@require_GET
def seo_scan_job_progress(request, job_id: int):
    _ensure_admin_control_enabled()
    job = get_object_or_404(SeoScanJob, pk=job_id)
    return JsonResponse(scan_job_progress(job))


@staff_member_required
@require_POST
def seo_scan_job_cancel(request, job_id: int):
    _ensure_admin_control_enabled()
    if not request.user.is_superuser:
        return JsonResponse({"ok": False, "message": "Superuser required."}, status=403)
    job = get_object_or_404(SeoScanJob, pk=job_id)
    ok = cancel_scan_job(job)
    if request.htmx:
        return JsonResponse({"ok": ok, "job_id": job.id})
    if ok:
        messages.warning(request, f"Scan job #{job.id} cancel requested.")
    else:
        messages.info(request, f"Scan job #{job.id} is not cancelable.")
    return _control_redirect("scan", job_id=job.id)


@staff_member_required
@require_GET
def seo_interlinks(request):
    _ensure_admin_control_enabled()
    return _control_redirect("interlinking")


@staff_member_required
@require_GET
def seo_queue(request):
    _ensure_admin_control_enabled()
    context = _admin_control_context(
        section="seo_queue",
        title="SEO Audit Queue",
        subtitle="Review on-site SEO, redirects, interlinking, and metadata queues in separate sections.",
    )
    context.update(_control_common_context(request))
    context["active_section"] = "onsite"
    return render(request, "seo/admin/control.html", context)


@staff_member_required
@require_POST
def seo_queue_single_action(request, suggestion_id: int, action: str):
    return seo_control_suggestion_action(request, suggestion_id=suggestion_id, action=action)


@staff_member_required
def seo_queue_edit(request, suggestion_id: int):
    return seo_control_suggestion_edit(request, suggestion_id=suggestion_id)


@staff_member_required
@require_POST
def seo_queue_bulk(request):
    return seo_control_suggestion_bulk(request)


@staff_member_required
@require_GET
def taxonomy_synonyms(request):
    _ensure_admin_control_enabled()
    return _control_redirect("settings")


@staff_member_required
@require_POST
def taxonomy_synonym_group_create(request):
    _ensure_admin_control_enabled()
    form = TaxonomySynonymGroupForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Synonym group created.")
    else:
        messages.error(request, "Could not create synonym group.")
    return _control_redirect("settings")


@staff_member_required
@require_POST
def taxonomy_synonym_term_add(request, group_id: int):
    _ensure_admin_control_enabled()
    group = get_object_or_404(TaxonomySynonymGroup, pk=group_id)
    form = TaxonomySynonymTermAddForm(request.POST)
    if form.is_valid():
        term = TaxonomySynonymTerm(
            group=group,
            term=form.cleaned_data["term"],
            is_canonical=form.cleaned_data.get("is_canonical", False),
            weight=form.cleaned_data.get("weight", 1.0) or 1.0,
            is_active=form.cleaned_data.get("is_active", True),
        )
        term.save()
        messages.success(request, "Synonym term added.")
    else:
        messages.error(request, "Could not add term.")
    return _control_redirect("settings")


@staff_member_required
@require_POST
def taxonomy_synonym_term_remove(request, group_id: int):
    _ensure_admin_control_enabled()
    group = get_object_or_404(TaxonomySynonymGroup, pk=group_id)
    term_id = request.POST.get("term_id")
    try:
        term_pk = int(term_id)
    except (TypeError, ValueError):
        messages.error(request, "Invalid term id.")
        return _control_redirect("settings")
    term = get_object_or_404(TaxonomySynonymTerm, pk=term_pk, group=group)
    term.delete()
    messages.success(request, "Synonym term removed.")
    return _control_redirect("settings")


@staff_member_required
@require_POST
def taxonomy_synonym_import(request):
    _ensure_admin_control_enabled()
    form = TaxonomySynonymImportForm(request.POST)
    if form.is_valid():
        result = import_synonyms_payload(form.cleaned_data["payload"])
        messages.success(
            request,
            f"Imported synonyms. Groups: {result['created_groups']}, terms: {result['created_terms']}.",
        )
    else:
        messages.error(request, "Import failed. Check payload format.")
    return _control_redirect("settings")


@staff_member_required
@require_GET
def taxonomy_synonym_export(request):
    _ensure_admin_control_enabled()
    payload = export_synonyms_payload()
    body = json.dumps(payload, indent=2, sort_keys=True)
    response = HttpResponse(body, content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="taxonomy-synonyms.json"'
    return response
