"""
SEO Views — POST handlers, CRUD, scan/job management, and taxonomy.

All write-oriented views for the SEO admin control center.
Split from admin_config_views.py for maintainability.
"""
from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from core.models import SeoSettings

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
    run_scan_job,
    scan_job_progress,
    start_full_scan,
)
from .models import (
    SeoEngineSettings,
    SeoScanJob,
    SeoSuggestion,
    SeoSuggestionRevision,
    TaxonomySynonymGroup,
    TaxonomySynonymTerm,
)
from .seo_views_helpers import (
    _admin_control_context,
    _control_redirect,
    _control_url,
    _ensure_admin_control_enabled,
    _resolve_return_section,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Automation / scan controls
# ---------------------------------------------------------------------------


@staff_member_required
@require_POST
def seo_control_run(request: HttpRequest) -> HttpResponseRedirect:
    """Run a full automation scan."""
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
def seo_control_autopilot(request: HttpRequest) -> HttpResponseRedirect:
    """Auto-approve safe suggestions above confidence threshold."""
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


# ---------------------------------------------------------------------------
# Settings save
# ---------------------------------------------------------------------------


@staff_member_required
@require_POST
def seo_control_settings_save(request: HttpRequest) -> HttpResponseRedirect:
    """Save SEO engine + defaults settings from the control center."""
    _ensure_admin_control_enabled()
    engine = SeoEngineSettings.get_solo()
    defaults_obj = SeoSettings.get_solo()
    fields: list[str] = []
    seo_fields: list[str] = []

    def parse_checkbox(name: str, current: bool) -> bool:
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


# ---------------------------------------------------------------------------
# Job progress
# ---------------------------------------------------------------------------


@staff_member_required
@require_GET
def seo_control_job_progress(request: HttpRequest, job_id: int) -> JsonResponse:
    """Return scan job progress as JSON."""
    _ensure_admin_control_enabled()
    job = get_object_or_404(SeoScanJob, pk=job_id)
    return JsonResponse(scan_job_progress(job))


# ---------------------------------------------------------------------------
# Suggestion CRUD
# ---------------------------------------------------------------------------


@staff_member_required
@require_POST
def seo_control_suggestion_action(request: HttpRequest, suggestion_id: int, action: str) -> HttpResponseRedirect:
    """Approve or reject a single suggestion."""
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
def seo_control_suggestion_edit(request: HttpRequest, suggestion_id: int) -> HttpResponse:
    """Edit a suggestion payload before decision."""
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
def seo_control_suggestion_bulk(request: HttpRequest) -> HttpResponseRedirect:
    """Bulk approve/reject selected suggestions."""
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


# ---------------------------------------------------------------------------
# Scan start / cancel
# ---------------------------------------------------------------------------


@staff_member_required
@require_POST
def seo_scan_start(request: HttpRequest) -> HttpResponseRedirect | JsonResponse:
    """Start a new SEO scan job."""
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
def seo_interlink_scan_start(request: HttpRequest) -> HttpResponseRedirect | JsonResponse:
    """Start a new internal linking scan job."""
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
@require_POST
def seo_scan_job_cancel(request: HttpRequest, job_id: int) -> HttpResponseRedirect | JsonResponse:
    """Cancel a running scan job."""
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


# ---------------------------------------------------------------------------
# Taxonomy (synonyms)
# ---------------------------------------------------------------------------


@staff_member_required
@require_GET
def taxonomy_synonyms(request: HttpRequest) -> HttpResponseRedirect:
    """Redirect to settings tab (synonyms are managed there now)."""
    _ensure_admin_control_enabled()
    return _control_redirect("settings")


@staff_member_required
@require_POST
def taxonomy_synonym_group_create(request: HttpRequest) -> HttpResponseRedirect:
    """Create a new synonym group."""
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
def taxonomy_synonym_term_add(request: HttpRequest, group_id: int) -> HttpResponseRedirect:
    """Add a term to an existing synonym group."""
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
def taxonomy_synonym_term_remove(request: HttpRequest, group_id: int) -> HttpResponseRedirect:
    """Remove a term from a synonym group."""
    _ensure_admin_control_enabled()
    group = get_object_or_404(TaxonomySynonymGroup, pk=group_id)
    term_id = request.POST.get("term_id")
    try:
        term_pk = int(term_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        messages.error(request, "Invalid term id.")
        return _control_redirect("settings")
    term = get_object_or_404(TaxonomySynonymTerm, pk=term_pk, group=group)
    term.delete()
    messages.success(request, "Synonym term removed.")
    return _control_redirect("settings")


@staff_member_required
@require_POST
def taxonomy_synonym_import(request: HttpRequest) -> HttpResponseRedirect:
    """Import synonym groups from JSON payload."""
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
def taxonomy_synonym_export(request: HttpRequest) -> HttpResponse:
    """Export all synonym groups as a downloadable JSON file."""
    _ensure_admin_control_enabled()
    payload = export_synonyms_payload()
    body = json.dumps(payload, indent=2, sort_keys=True)
    response = HttpResponse(body, content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="taxonomy-synonyms.json"'
    return response
