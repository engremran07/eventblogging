"""
SEO Views — Control center shell and per-tab context builders.

Handles the main control center GET views and lazy-loaded tab partials.
Split from admin_config_views.py for maintainability.
"""
from __future__ import annotations

import logging
from typing import Any

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.models import SeoSettings

from .admin_config_services import queue_snapshot, scan_job_progress, seo_overview_with_queue
from .models import SeoEngineSettings, SeoScanJob, SeoSuggestion, TaxonomySynonymGroup
from .seo_views_helpers import (
    ONSITE_SUGGESTIONS_PAGE_SIZE,
    ONSITE_TASKS_PAGE_SIZE,
    _admin_control_context,
    _control_redirect,
    _enriched_issue_feed,
    _ensure_admin_control_enabled,
    _interlink_edge_rows,
    _interlink_metrics,
    _interlink_suggestion_rows,
    _normalize_control_section,
    _open_issue_target_refs,
    _paginate_rows,
    _pending_tasks,
    _query_without_keys,
    _queue_counts_for_suggestions,
    _queue_counts_from_rows,
    _seo_issue_rows,
    _suggestion_rows,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-tab lean context builders — only load what each tab needs
# ---------------------------------------------------------------------------


def _tab_context_discrepancies(request: HttpRequest) -> dict[str, Any]:
    """Context for the Discrepancies tab — posts/pages with SEO issues."""
    settings_obj = SeoEngineSettings.get_solo()
    open_seo_issue_targets = _open_issue_target_refs(domain="seo")
    pending_task_rows, _pending_task_summary = _pending_tasks(limit_suggestions=None, limit_issues=None)

    onsite_excluded_types = [
        SeoSuggestion.SuggestionType.METADATA,
        SeoSuggestion.SuggestionType.INTERLINK,
    ]

    # SEO issues (discrepancies)
    pending_seo_tasks_all = [
        row for row in pending_task_rows
        if row["domain"] == "seo"
        and (row.get("target_content_type_id"), row.get("target_object_id")) in open_seo_issue_targets
    ]
    pending_seo_task_page_obj, pending_seo_task_rows = _paginate_rows(
        request, pending_seo_tasks_all, param="onsite_page", page_size=ONSITE_TASKS_PAGE_SIZE,
    )

    # Suggestions for discrepancies
    onsite_suggestion_rows_all = [
        row for row in _suggestion_rows(exclude_suggestion_types=onsite_excluded_types, limit=None)
        if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
    ]
    onsite_suggestion_page_obj, onsite_suggestion_rows = _paginate_rows(
        request, onsite_suggestion_rows_all, param="onsite_suggestion_page",
        page_size=ONSITE_SUGGESTIONS_PAGE_SIZE,
    )

    # Scan jobs
    scan_jobs_qs = SeoScanJob.objects.exclude(
        job_type=SeoScanJob.JobType.INTERLINKS
    ).order_by("-created_at")
    scan_jobs = scan_jobs_qs[:50]
    selected_scan_job = scan_jobs_qs.first()

    return {
        "pending_seo_task_rows": pending_seo_task_rows,
        "pending_seo_task_page_obj": pending_seo_task_page_obj,
        "pending_seo_task_summary": {
            "total": len(pending_seo_tasks_all),
            "high": sum(1 for row in pending_seo_tasks_all if row["priority"] == "high"),
        },
        "onsite_suggestion_rows": onsite_suggestion_rows,
        "onsite_suggestion_page_obj": onsite_suggestion_page_obj,
        "onsite_queue_counts": _queue_counts_from_rows(onsite_suggestion_rows_all),
        "seo_issue_rows": _seo_issue_rows(),
        "latest_issues": _enriched_issue_feed(),
        "scan_jobs": scan_jobs,
        "selected_scan_job": selected_scan_job,
        "selected_scan_job_progress": scan_job_progress(selected_scan_job) if selected_scan_job else None,
        "selected_scan_items": (
            selected_scan_job.items.select_related("content_type").order_by("-id")[:180]
            if selected_scan_job else []
        ),
        "job_types": [
            (value, label) for value, label in SeoScanJob.JobType.choices
            if value != SeoScanJob.JobType.INTERLINKS
        ],
        "engine_settings": settings_obj,
        "onsite_page_query": _query_without_keys(request, "onsite_page"),
        "onsite_suggestion_page_query": _query_without_keys(request, "onsite_suggestion_page"),
        "control_querystring": request.GET.urlencode(),
    }


def _tab_context_interlinking(request: HttpRequest) -> dict[str, Any]:
    """Context for the Interlinking tab."""
    job_id = (request.GET.get("job_id") or "").strip()
    interlink_jobs_qs = SeoScanJob.objects.filter(
        job_type=SeoScanJob.JobType.INTERLINKS
    ).order_by("-created_at")
    interlink_jobs = interlink_jobs_qs[:50]
    selected_interlink_job = None
    if job_id.isdigit():
        selected_interlink_job = SeoScanJob.objects.filter(pk=int(job_id)).first()
    if not selected_interlink_job:
        selected_interlink_job = interlink_jobs_qs.first()

    pending_task_rows, _ = _pending_tasks(limit_suggestions=None, limit_issues=None)
    pending_interlink_tasks = [row for row in pending_task_rows if row["domain"] == "internal_linking"][:160]

    return {
        "interlink_metrics": _interlink_metrics(),
        "interlink_edge_rows": _interlink_edge_rows(),
        "interlink_suggestion_rows": _interlink_suggestion_rows(),
        "interlink_jobs": interlink_jobs,
        "selected_interlink_job": selected_interlink_job,
        "selected_interlink_job_progress": (
            scan_job_progress(selected_interlink_job) if selected_interlink_job else None
        ),
        "selected_interlink_items": (
            selected_interlink_job.items.select_related("content_type").order_by("-id")[:180]
            if selected_interlink_job else []
        ),
        "pending_interlink_task_rows": pending_interlink_tasks,
        "interlink_queue_counts": _queue_counts_for_suggestions(
            suggestion_types=[SeoSuggestion.SuggestionType.INTERLINK],
        ),
        "engine_settings": SeoEngineSettings.get_solo(),
        "control_querystring": request.GET.urlencode(),
    }


def _tab_context_metadata(request: HttpRequest) -> dict[str, Any]:
    """Context for the Metadata tab."""
    defaults_obj = SeoSettings.get_solo()
    metadata_types = [SeoSuggestion.SuggestionType.METADATA]
    pending_task_rows, _ = _pending_tasks(limit_suggestions=None, limit_issues=None)
    pending_metadata_tasks = [row for row in pending_task_rows if row["domain"] == "metadata"][:160]

    return {
        "pending_metadata_task_rows": pending_metadata_tasks,
        "metadata_suggestion_rows": _suggestion_rows(suggestion_types=metadata_types, limit=300),
        "metadata_queue_counts": _queue_counts_for_suggestions(suggestion_types=metadata_types),
        "metadata_template_injection": {
            "canonical": bool(defaults_obj.canonical_base_url.strip()),
            "open_graph": bool(defaults_obj.enable_open_graph),
            "twitter_cards": bool(defaults_obj.enable_twitter_cards),
            "organization_schema": bool(defaults_obj.organization_schema_name.strip()),
        },
        "seo_defaults": defaults_obj,
        "engine_settings": SeoEngineSettings.get_solo(),
        "control_querystring": request.GET.urlencode(),
    }


def _tab_context_redirects(request: HttpRequest) -> dict[str, Any]:
    """Context for the Redirects tab."""
    redirect_types = [SeoSuggestion.SuggestionType.REDIRECT]
    open_seo_issue_targets = _open_issue_target_refs(domain="seo")
    pending_task_rows, _ = _pending_tasks(limit_suggestions=None, limit_issues=None)

    redirect_suggestion_rows_all = [
        row for row in _suggestion_rows(suggestion_types=redirect_types, limit=None)
        if (row.get("content_type_id"), row.get("object_id")) in open_seo_issue_targets
    ]
    redirect_suggestion_page_obj, redirect_suggestion_rows = _paginate_rows(
        request, redirect_suggestion_rows_all, param="redirect_page",
        page_size=ONSITE_SUGGESTIONS_PAGE_SIZE,
    )

    pending_redirect_tasks_all = [
        row for row in pending_task_rows
        if row["domain"] == "seo"
        and row["task_kind"] == "suggestion"
        and (row.get("target_content_type_id"), row.get("target_object_id")) in open_seo_issue_targets
    ]
    pending_redirect_task_page_obj, pending_redirect_task_rows = _paginate_rows(
        request, pending_redirect_tasks_all, param="redirect_task_page",
        page_size=ONSITE_TASKS_PAGE_SIZE,
    )

    return {
        "redirect_suggestion_rows": redirect_suggestion_rows,
        "redirect_suggestion_page_obj": redirect_suggestion_page_obj,
        "redirect_queue_counts": _queue_counts_from_rows(redirect_suggestion_rows_all),
        "pending_redirect_task_rows": pending_redirect_task_rows,
        "pending_redirect_task_page_obj": pending_redirect_task_page_obj,
        "pending_redirect_task_summary": {
            "total": len(pending_redirect_tasks_all),
            "high": sum(1 for row in pending_redirect_tasks_all if row["priority"] == "high"),
        },
        "redirect_task_page_query": _query_without_keys(request, "redirect_task_page"),
        "redirect_page_query": _query_without_keys(request, "redirect_page"),
        "engine_settings": SeoEngineSettings.get_solo(),
        "control_querystring": request.GET.urlencode(),
    }


def _tab_context_settings(request: HttpRequest) -> dict[str, Any]:
    """Context for the Settings tab."""
    return {
        "engine_settings": SeoEngineSettings.get_solo(),
        "seo_defaults": SeoSettings.get_solo(),
        "synonym_groups": TaxonomySynonymGroup.objects.prefetch_related("terms").order_by("scope", "name")[:40],
        "control_querystring": request.GET.urlencode(),
    }


# ---------------------------------------------------------------------------
# Control center views
# ---------------------------------------------------------------------------


@staff_member_required
@require_GET
def seo_control_center(request: HttpRequest, section: str | None = None) -> HttpResponse:
    """Render the SEO control center shell page."""
    _ensure_admin_control_enabled()
    active_section = _normalize_control_section(section or request.GET.get("section") or "discrepancies")
    context = _admin_control_context(
        section="seo_control",
        title="SEO Control",
        subtitle="Discrepancies, interlinking, metadata, and redirects dashboard.",
    )
    # Only load KPIs + top-level counts for the shell; tab content is lazily loaded via HTMX.
    context["seo_overview"] = seo_overview_with_queue()
    context["queue_counts"] = queue_snapshot()
    context["interlink_metrics"] = _interlink_metrics()
    context["active_section"] = active_section
    context["control_querystring"] = request.GET.urlencode()
    return render(request, "seo/admin/control.html", context)


@staff_member_required
@require_GET
def seo_control_section(request: HttpRequest, section: str) -> HttpResponse:
    """Render an individual tab partial for the SEO control center (HTMX only)."""
    _ensure_admin_control_enabled()

    # HTMX guard — non-HTMX requests get the full shell page instead
    if not getattr(request, "htmx", None):
        return _control_redirect(section)

    safe_section = _normalize_control_section(section, default="")
    if not safe_section:
        raise Http404("Unknown SEO section.")

    _TAB_CONTEXT_BUILDERS: dict[str, Any] = {
        "discrepancies": _tab_context_discrepancies,
        "interlinking": _tab_context_interlinking,
        "metadata": _tab_context_metadata,
        "redirects": _tab_context_redirects,
        "settings": _tab_context_settings,
    }
    _TAB_TEMPLATES: dict[str, str] = {
        "discrepancies": "seo/admin/partials/seo_control_discrepancies.html",
        "interlinking": "seo/admin/partials/seo_control_interlinking.html",
        "metadata": "seo/admin/partials/seo_control_metadata.html",
        "redirects": "seo/admin/partials/seo_control_redirects.html",
        "settings": "seo/admin/partials/seo_control_settings.html",
    }

    builder = _TAB_CONTEXT_BUILDERS.get(safe_section)
    template = _TAB_TEMPLATES.get(safe_section)

    if not builder or not template:
        raise Http404(f"Unknown SEO section: {safe_section}")

    context = builder(request)
    context["active_section"] = safe_section
    return render(request, template, context)
