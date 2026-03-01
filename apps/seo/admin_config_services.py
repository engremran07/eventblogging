from __future__ import annotations

import json
from copy import deepcopy
from datetime import timedelta
from time import monotonic

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count
from django.forms.models import model_to_dict
from django.utils import timezone

from blog.models import Post
from pages.models import Page

from .models import (
    SeoEngineSettings,
    SeoScanJob,
    SeoScanJobItem,
    SeoSuggestion,
    SeoSuggestionRevision,
    TaxonomySynonymGroup,
    TaxonomySynonymTerm,
)
from .services import approve_suggestion, audit_content, reject_suggestion, seo_overview_metrics
from .synonyms import clear_synonym_cache, normalize_term


def _target_queryset_for_job_type(job_type: str):
    if job_type == SeoScanJob.JobType.POSTS:
        return Post.objects.order_by("id"), Page.objects.none()
    if job_type == SeoScanJob.JobType.PAGES:
        return Post.objects.none(), Page.objects.order_by("id")
    if job_type == SeoScanJob.JobType.CHANGED_ONLY:
        threshold_days = max(SeoEngineSettings.get_solo().stale_days_threshold, 1)
        cutoff = timezone.now() - timedelta(days=threshold_days)
        return (
            Post.objects.filter(updated_at__gte=cutoff).order_by("id"),
            Page.objects.filter(updated_at__gte=cutoff).order_by("id"),
        )
    if job_type == SeoScanJob.JobType.INTERLINKS:
        return Post.objects.order_by("id"), Page.objects.order_by("id")
    return Post.objects.order_by("id"), Page.objects.order_by("id")


def _build_scan_items(job: SeoScanJob):
    post_qs, page_qs = _target_queryset_for_job_type(job.job_type)
    post_ct = ContentType.objects.get_for_model(Post)
    page_ct = ContentType.objects.get_for_model(Page)
    items = [
        SeoScanJobItem(
            job=job,
            content_type=post_ct,
            object_id=post.id,
            url=post.get_absolute_url(),
        )
        for post in post_qs.only("id", "slug")
    ]
    items.extend(
        SeoScanJobItem(
            job=job,
            content_type=page_ct,
            object_id=page.id,
            url=page.get_absolute_url(),
        )
        for page in page_qs.only("id", "slug")
    )
    return items


def _engine_snapshot():
    settings = SeoEngineSettings.get_solo()
    field_names = [field.name for field in settings._meta.fields if field.name not in {"id"}]
    return model_to_dict(settings, fields=field_names)


@transaction.atomic
def create_scan_job(*, job_type: str, started_by=None, trigger: str = SeoScanJob.Trigger.MANUAL, notes: str = ""):
    job = SeoScanJob.objects.create(
        job_type=job_type,
        status=SeoScanJob.Status.QUEUED,
        trigger=trigger,
        started_by=started_by if getattr(started_by, "is_authenticated", False) else None,
        settings_snapshot_json=_engine_snapshot(),
        notes=notes,
    )
    items = _build_scan_items(job)
    if items:
        SeoScanJobItem.objects.bulk_create(items, batch_size=500)
    job.total_items = len(items)
    job.save(update_fields=["total_items", "updated_at"])
    return job


def _complete_job(job: SeoScanJob, *, status: str, last_error: str = ""):
    job.status = status
    job.finished_at = timezone.now()
    if last_error:
        job.last_error = last_error
    job.save(update_fields=["status", "finished_at", "last_error", "updated_at"])


def run_scan_job(job_id: int):
    job = SeoScanJob.objects.filter(pk=job_id).first()
    if not job:
        return {"ok": False, "reason": "missing_job", "job_id": job_id}
    if job.status not in {SeoScanJob.Status.QUEUED, SeoScanJob.Status.RUNNING}:
        return {"ok": False, "reason": "job_not_runnable", "status": job.status}
    if job.total_items == 0:
        _complete_job(job, status=SeoScanJob.Status.COMPLETED)
        return {"ok": True, "job_id": job.id, "processed": 0, "empty": True}

    job.status = SeoScanJob.Status.RUNNING
    if not job.started_at:
        job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])

    # Resume-safe counters: continue from persisted progress when rerunning an in-flight job.
    processed = int(job.processed_items or 0)
    errors = int(job.error_count or 0)
    warnings = int(job.warning_count or 0)
    snapshots = int(job.snapshot_count or 0)
    for item in job.items.filter(status=SeoScanJobItem.Status.PENDING).select_related("content_type"):
        if job.canceled_requested:
            _complete_job(job, status=SeoScanJob.Status.CANCELED)
            return {
                "ok": True,
                "job_id": job.id,
                "processed": processed,
                "canceled": True,
            }
        item.status = SeoScanJobItem.Status.RUNNING
        item.started_at = timezone.now()
        item.save(update_fields=["status", "started_at"])

        model_name = item.content_type.model
        start = monotonic()
        snapshot = None
        error_text = ""
        try:
            snapshot = audit_content(model_name, item.object_id, trigger="scheduled")
        except Exception as exc:
            error_text = str(exc)
        duration_ms = int((monotonic() - start) * 1000)

        if snapshot is None:
            item.status = SeoScanJobItem.Status.FAILED
            item.error_text = error_text or "Snapshot was not generated."
            item.duration_ms = duration_ms
            item.finished_at = timezone.now()
            item.save(update_fields=["status", "error_text", "duration_ms", "finished_at"])
            errors += 1
        else:
            item.status = SeoScanJobItem.Status.COMPLETED
            item.score = snapshot.score
            item.critical_count = snapshot.critical_count
            item.warning_count = snapshot.warning_count
            item.duration_ms = duration_ms
            item.finished_at = timezone.now()
            item.save(
                update_fields=[
                    "status",
                    "score",
                    "critical_count",
                    "warning_count",
                    "duration_ms",
                    "finished_at",
                ]
            )
            warnings += snapshot.warning_count
            snapshots += 1

        processed += 1
        SeoScanJob.objects.filter(pk=job.pk).update(
            processed_items=processed,
            error_count=errors,
            warning_count=warnings,
            snapshot_count=snapshots,
            updated_at=timezone.now(),
        )
        job.refresh_from_db(fields=["canceled_requested"])

    _complete_job(job, status=SeoScanJob.Status.COMPLETED)
    return {
        "ok": True,
        "job_id": job.id,
        "processed": processed,
        "errors": errors,
        "warnings": warnings,
        "snapshots": snapshots,
    }


def enqueue_scan_job(job_id: int):
    from .tasks import seo_run_scan_job

    try:
        seo_run_scan_job.delay(job_id)
        return {"ok": True, "queued": True}
    except Exception:
        result = run_scan_job(job_id)
        result["queued"] = False
        return result


def scan_job_progress(job: SeoScanJob):
    summary = {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "trigger": job.trigger,
        "started_at": job.started_at.isoformat() if job.started_at else "",
        "finished_at": job.finished_at.isoformat() if job.finished_at else "",
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "error_count": job.error_count,
        "warning_count": job.warning_count,
        "snapshot_count": job.snapshot_count,
        "progress_percent": job.progress_percent,
        "canceled_requested": job.canceled_requested,
    }
    current_item = (
        job.items.filter(status=SeoScanJobItem.Status.RUNNING)
        .order_by("-started_at", "-id")
        .values("id", "url", "content_type__model", "object_id")
        .first()
    )
    summary["current_item"] = current_item or {}
    return summary


def cancel_scan_job(job: SeoScanJob):
    if job.status not in {SeoScanJob.Status.QUEUED, SeoScanJob.Status.RUNNING}:
        return False
    job.canceled_requested = True
    job.save(update_fields=["canceled_requested", "updated_at"])
    return True


def queue_snapshot():
    suggestion_counts = (
        SeoSuggestion.objects.values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )
    counts = {row["status"]: row["total"] for row in suggestion_counts}
    return {
        "pending": counts.get(SeoSuggestion.Status.PENDING, 0),
        "needs_correction": counts.get(SeoSuggestion.Status.NEEDS_CORRECTION, 0),
        "approved": counts.get(SeoSuggestion.Status.APPLIED, 0),
        "rejected": counts.get(SeoSuggestion.Status.REJECTED, 0),
    }


@transaction.atomic
def edit_suggestion_payload(*, suggestion: SeoSuggestion, payload: dict, edited_by=None, note: str = ""):
    old_payload = deepcopy(suggestion.payload_json or {})
    suggestion.payload_json = payload
    suggestion.status = SeoSuggestion.Status.NEEDS_CORRECTION
    suggestion.save(update_fields=["payload_json", "status"])
    SeoSuggestionRevision.objects.create(
        suggestion=suggestion,
        edited_by=edited_by if getattr(edited_by, "is_authenticated", False) else None,
        old_payload_json=old_payload,
        new_payload_json=payload,
        note=note or "",
    )
    return suggestion


def apply_suggestion_decision(*, suggestion_id: int, action: str, reviewer=None):
    if action == "approve":
        return approve_suggestion(suggestion_id, reviewer=reviewer)
    if action == "reject":
        return reject_suggestion(suggestion_id)
    return {"ok": False, "message": "Unsupported action.", "status": 400}


def apply_suggestion_bulk(*, action: str, ids, reviewer=None):
    success = 0
    skipped = 0
    for raw_id in ids:
        try:
            suggestion_id = int(raw_id)
        except (TypeError, ValueError):
            skipped += 1
            continue
        result = apply_suggestion_decision(
            suggestion_id=suggestion_id,
            action=action,
            reviewer=reviewer,
        )
        if result.get("ok"):
            success += 1
        else:
            skipped += 1
    return {"success": success, "skipped": skipped}


def export_synonyms_payload():
    rows = []
    groups = TaxonomySynonymGroup.objects.prefetch_related("terms").order_by("scope", "name")
    for group in groups:
        terms = [
            {
                "id": term.id,
                "term": term.term,
                "normalized_term": term.normalized_term,
                "is_canonical": term.is_canonical,
                "weight": term.weight,
                "is_active": term.is_active,
            }
            for term in group.terms.order_by("-is_canonical", "-weight", "term")
        ]
        rows.append(
            {
                "id": group.id,
                "name": group.name,
                "scope": group.scope,
                "is_active": group.is_active,
                "terms": terms,
            }
        )
    return rows


@transaction.atomic
def import_synonyms_payload(payload):
    created_groups = 0
    created_terms = 0
    for raw_group in payload:
        if not isinstance(raw_group, dict):
            continue
        name = (raw_group.get("name") or "").strip()
        scope = raw_group.get("scope") or TaxonomySynonymGroup.Scope.ALL
        if not name:
            continue
        if scope not in TaxonomySynonymGroup.Scope.values:
            scope = TaxonomySynonymGroup.Scope.ALL
        group, created = TaxonomySynonymGroup.objects.get_or_create(
            name=name,
            scope=scope,
            defaults={"is_active": bool(raw_group.get("is_active", True))},
        )
        if created:
            created_groups += 1
        elif "is_active" in raw_group:
            group.is_active = bool(raw_group.get("is_active"))
            group.save(update_fields=["is_active", "updated_at"])

        for raw_term in raw_group.get("terms", []):
            if isinstance(raw_term, str):
                term_value = raw_term
                term_payload = {}
            elif isinstance(raw_term, dict):
                term_value = raw_term.get("term", "")
                term_payload = raw_term
            else:
                continue
            term_value = (term_value or "").strip()
            if not term_value:
                continue
            normalized = normalize_term(term_value)
            if not normalized:
                continue
            term, term_created = TaxonomySynonymTerm.objects.get_or_create(
                group=group,
                normalized_term=normalized,
                defaults={
                    "term": term_value,
                    "is_canonical": bool(term_payload.get("is_canonical", False)),
                    "weight": float(term_payload.get("weight", 1.0)),
                    "is_active": bool(term_payload.get("is_active", True)),
                },
            )
            if term_created:
                created_terms += 1
            else:
                term.term = term_value
                term.is_canonical = bool(term_payload.get("is_canonical", term.is_canonical))
                term.weight = float(term_payload.get("weight", term.weight))
                term.is_active = bool(term_payload.get("is_active", term.is_active))
                term.save(update_fields=["term", "is_canonical", "weight", "is_active", "updated_at"])
    clear_synonym_cache()
    return {"created_groups": created_groups, "created_terms": created_terms}


def seo_overview_with_queue():
    payload = seo_overview_metrics()
    payload["queue"] = queue_snapshot()
    payload["recent_jobs"] = list(
        SeoScanJob.objects.order_by("-created_at")
        .values(
            "id",
            "job_type",
            "status",
            "processed_items",
            "total_items",
            "error_count",
            "warning_count",
            "created_at",
            "finished_at",
        )[:12]
    )
    return payload


def dump_synonyms_json():
    return json.dumps(export_synonyms_payload(), indent=2, sort_keys=True)


def start_full_scan(*, started_by=None, notes: str = "", run_immediately: bool = True):
    job = create_scan_job(
        job_type=SeoScanJob.JobType.FULL,
        started_by=started_by,
        trigger=SeoScanJob.Trigger.MANUAL,
        notes=notes or "Central automation scan.",
    )
    if run_immediately:
        run_scan_job(job.id)
    else:
        enqueue_scan_job(job.id)
    job.refresh_from_db()
    return job


def auto_approve_safe_suggestions(*, reviewer=None, min_confidence: float = 0.82, limit: int = 300):
    queryset = (
        SeoSuggestion.objects.filter(
            status__in=[SeoSuggestion.Status.PENDING, SeoSuggestion.Status.NEEDS_CORRECTION],
            suggestion_type__in=[
                SeoSuggestion.SuggestionType.METADATA,
                SeoSuggestion.SuggestionType.INTERLINK,
            ],
            confidence__gte=min_confidence,
        )
        .order_by("-confidence", "created_at")[: max(int(limit), 1)]
    )
    approved = 0
    skipped = 0
    for suggestion in queryset:
        result = approve_suggestion(suggestion.id, reviewer=reviewer)
        if result.get("ok"):
            approved += 1
        else:
            skipped += 1
    return {
        "approved": approved,
        "skipped": skipped,
        "threshold": min_confidence,
        "considered": queryset.count(),
    }
