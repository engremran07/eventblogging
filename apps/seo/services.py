from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count
from django.utils import timezone

from blog.models import Post
from pages.models import Page

from .checks import run_checks
from .interlink import (
    apply_suggestions_to_markdown,
    build_interlink_suggestions,
    compute_link_budget,
)
from .metadata import resolve_metadata
from .models import (
    SeoAuditSnapshot,
    SeoEngineSettings,
    SeoIssue,
    SeoLinkEdge,
    SeoMetadataLock,
    SeoRedirectRule,
    SeoSuggestion,
)

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[a-zA-Z0-9]{2,}")


@dataclass
class ContentAdapter:
    pk: int
    model: type
    content_type: ContentType
    route_type: str
    title: str
    slug: str
    meta_title: str
    meta_description: str
    canonical_url: str
    body_markdown: str
    body_html: str
    word_count: int
    created_at: timezone.datetime | None
    updated_at: timezone.datetime | None
    published_at: timezone.datetime | None
    url: str
    summary: str
    excerpt: str
    og_image_url: str
    is_featured: bool
    status: str
    link_edge_model: type = SeoLinkEdge

    @property
    def excerpt_or_summary(self):
        return self.excerpt or self.summary

    @property
    def is_published(self):
        return (
            self.status == "published"
            and self.published_at is not None
            and self.published_at <= timezone.now()
        )

    def get_absolute_url(self):
        return self.url


def _content_type_for_instance(instance):
    return ContentType.objects.get_for_model(instance.__class__)


def _build_adapter_from_instance(instance):
    route_type = "other"
    summary = ""
    excerpt = ""
    og_image_url = ""

    if isinstance(instance, Post):
        route_type = "post"
        excerpt = instance.excerpt or ""
        if instance.cover_image:
            og_image_url = instance.cover_image.url
    elif isinstance(instance, Page):
        route_type = "page"
        summary = instance.summary or ""

    return ContentAdapter(
        pk=instance.pk,
        model=instance.__class__,
        content_type=_content_type_for_instance(instance),
        route_type=route_type,
        title=instance.title or "",
        slug=instance.slug or "",
        meta_title=getattr(instance, "meta_title", "") or "",
        meta_description=getattr(instance, "meta_description", "") or "",
        canonical_url=getattr(instance, "canonical_url", "") or "",
        body_markdown=instance.body_markdown or "",
        body_html=instance.body_html or "",
        word_count=getattr(instance, "word_count", 0) or 0,
        created_at=getattr(instance, "created_at", None),
        updated_at=getattr(instance, "updated_at", None),
        published_at=getattr(instance, "published_at", None),
        url=instance.get_absolute_url(),
        summary=summary,
        excerpt=excerpt,
        og_image_url=og_image_url,
        is_featured=bool(getattr(instance, "is_featured", False)),
        status=getattr(instance, "status", "") or "",
    )


def build_adapter_from_instance(instance):
    return _build_adapter_from_instance(instance)


def _normalize_text(text: str):
    return " ".join((text or "").split()).strip()


def _clip(text: str, limit: int):
    return _normalize_text(text)[:limit]


def build_route_adapter(
    *,
    route_type: str,
    title: str,
    description: str = "",
    body_markdown: str = "",
    url: str = "/",
    updated_at=None,
    published_at=None,
    canonical_url: str = "",
    og_image_url: str = "",
):
    model = Page if route_type in {"page", "policy"} else Post
    content_type = ContentType.objects.get_for_model(model)
    safe_title = _clip(title, 220) or "Untitled"
    safe_description = _clip(description, 320)
    body = body_markdown or ""
    word_count = max(len(TOKEN_RE.findall(body)), 0)
    now = timezone.now()
    return ContentAdapter(
        pk=0,
        model=model,
        content_type=content_type,
        route_type=route_type,
        title=safe_title,
        slug="",
        meta_title=safe_title[:70],
        meta_description=safe_description[:170],
        canonical_url=canonical_url,
        body_markdown=body,
        body_html="",
        word_count=word_count,
        created_at=updated_at or now,
        updated_at=updated_at or now,
        published_at=published_at,
        url=url or "/",
        summary=safe_description,
        excerpt=safe_description,
        og_image_url=og_image_url or "",
        is_featured=False,
        status="published" if published_at else "draft",
    )


def resolve_metadata_for_instance(instance, *, request=None):
    adapter = _build_adapter_from_instance(instance)
    return resolve_metadata(adapter, request=request).to_dict()


def resolve_metadata_for_route(
    request,
    *,
    route_type: str,
    title: str,
    description: str = "",
    body_markdown: str = "",
    canonical_url: str = "",
    og_image_url: str = "",
):
    adapter = build_route_adapter(
        route_type=route_type,
        title=title,
        description=description,
        body_markdown=body_markdown,
        url=request.path if request else "/",
        canonical_url=canonical_url,
        og_image_url=og_image_url,
        updated_at=timezone.now(),
        published_at=timezone.now(),
    )
    return resolve_metadata(adapter, request=request).to_dict()


def metadata_template_payload(metadata: dict):
    metadata = metadata or {}
    json_ld = metadata.get("json_ld") or []
    json_ld_serialized = [
        json.dumps(node, ensure_ascii=False, separators=(",", ":")) for node in json_ld
    ]
    return {
        "resolved_seo": metadata,
        "resolved_seo_json_ld": json_ld_serialized,
    }


def seo_context_for_instance(instance, *, request=None):
    return metadata_template_payload(resolve_metadata_for_instance(instance, request=request))


def seo_context_for_route(
    request,
    *,
    route_type: str,
    title: str,
    description: str = "",
    body_markdown: str = "",
    canonical_url: str = "",
    og_image_url: str = "",
):
    metadata = resolve_metadata_for_route(
        request,
        route_type=route_type,
        title=title,
        description=description,
        body_markdown=body_markdown,
        canonical_url=canonical_url,
        og_image_url=og_image_url,
    )
    return metadata_template_payload(metadata)


def _get_instance(content_type: str, object_id: int):
    if content_type == "post":
        return Post.objects.filter(pk=object_id).first()
    if content_type == "page":
        return Page.objects.filter(pk=object_id).first()
    return None


def _serialize_check_result(result):
    return {
        "key": result.key,
        "severity": result.severity,
        "passed": result.passed,
        "message": result.message,
        "suggested_fix": result.suggested_fix,
        "autofixable": result.autofixable,
        "details": result.details,
    }


def _score_from_results(results):
    total = len(results) or 1
    passed = sum(1 for row in results if row.passed)
    critical_count = sum(1 for row in results if not row.passed and row.severity == "critical")
    warning_count = sum(1 for row in results if not row.passed and row.severity == "warning")
    failed_count = total - passed
    score = (passed / total) * 100.0
    score -= critical_count * 6.0
    score -= warning_count * 2.0
    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 2),
        "passed_count": passed,
        "failed_count": failed_count,
        "critical_count": critical_count,
        "warning_count": warning_count,
    }


def _checksum(adapter: ContentAdapter, metadata: dict, results):
    payload = {
        "id": f"{adapter.route_type}:{adapter.pk}",
        "updated_at": adapter.updated_at.isoformat() if adapter.updated_at else "",
        "meta": metadata,
        "results": [_serialize_check_result(row) for row in results],
    }
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _target_pool(source_adapter: ContentAdapter):
    targets = []
    for post in Post.objects.published().only(
        "id",
        "title",
        "excerpt",
        "slug",
        "body_markdown",
        "body_html",
        "word_count",
        "published_at",
        "updated_at",
        "created_at",
        "status",
        "is_featured",
    )[:250]:
        if source_adapter.route_type == "post" and source_adapter.pk == post.pk:
            continue
        targets.append(_build_adapter_from_instance(post))
    for page in Page.objects.published().only(
        "id",
        "title",
        "summary",
        "slug",
        "body_markdown",
        "body_html",
        "word_count",
        "published_at",
        "updated_at",
        "created_at",
        "status",
        "is_featured",
    )[:250]:
        if source_adapter.route_type == "page" and source_adapter.pk == page.pk:
            continue
        targets.append(_build_adapter_from_instance(page))
    return targets


def _build_metadata_suggestion(adapter: ContentAdapter, metadata: dict):
    payload = {
        "meta_title": metadata.get("title", "")[:70],
        "meta_description": metadata.get("description", "")[:170],
        "canonical_url": metadata.get("canonical", ""),
    }
    SeoSuggestion.objects.create(
        content_type=adapter.content_type,
        object_id=adapter.pk,
        suggestion_type=SeoSuggestion.SuggestionType.METADATA,
        payload_json=payload,
        confidence=0.86,
    )


def _metadata_lock_for_target(content_type, object_id):
    return SeoMetadataLock.objects.filter(content_type=content_type, object_id=object_id).first()


def _apply_metadata_payload(target, payload: dict, lock: SeoMetadataLock | None):
    changed_fields = []
    title = _clip(payload.get("meta_title", ""), 70)
    description = _clip(payload.get("meta_description", ""), 170)
    canonical = _normalize_text(payload.get("canonical_url", ""))

    if title and not (lock and lock.lock_title):
        target.meta_title = title
        changed_fields.append("meta_title")
    if description and not (lock and lock.lock_description):
        target.meta_description = description
        changed_fields.append("meta_description")
    if canonical and not (lock and lock.lock_canonical):
        target.canonical_url = canonical
        changed_fields.append("canonical_url")

    if changed_fields:
        target._seo_skip_signal = True
        target.save(update_fields=[*changed_fields, "updated_at"])
        target._seo_skip_signal = False
    return changed_fields


def _persist_interlink_suggestions(adapter: ContentAdapter, suggestions):
    rows = [
        SeoSuggestion(
            content_type=adapter.content_type,
            object_id=adapter.pk,
            suggestion_type=SeoSuggestion.SuggestionType.INTERLINK,
            payload_json=suggestion,
            confidence=float(suggestion.get("score", 0.0)),
            status=SeoSuggestion.Status.PENDING,
        )
        for suggestion in suggestions
    ]
    if rows:
        SeoSuggestion.objects.bulk_create(rows)
    for suggestion in suggestions:
        target_type = suggestion.get("target_type")
        target_model = Post if target_type == "post" else Page
        target_ct = ContentType.objects.get_for_model(target_model)
        SeoLinkEdge.objects.create(
            source_content_type=adapter.content_type,
            source_object_id=adapter.pk,
            target_content_type=target_ct,
            target_object_id=int(suggestion.get("target_id", 0)),
            anchor_text=suggestion.get("anchor_text", "")[:180],
            source_fragment_hash=hashlib.sha1(
                suggestion.get("anchor_text", "").encode("utf-8")
            ).hexdigest()[:40],
            confidence=float(suggestion.get("score", 0.0)),
            status=SeoLinkEdge.Status.SUGGESTED,
        )


def _apply_interlinks(adapter: ContentAdapter, suggestions, settings: SeoEngineSettings):
    if not settings.apply_interlinks_on_audit:
        return 0
    if adapter.is_published and not settings.auto_update_published_links:
        return 0
    if not suggestions:
        return 0

    instance = _get_instance(adapter.route_type, adapter.pk)
    if not instance:
        return 0
    budget = compute_link_budget(
        total_docs=max(Post.objects.published().count() + Page.objects.published().count(), 1),
        word_count=adapter.word_count,
        min_links=settings.min_links_per_doc,
        whitehat_cap=settings.whitehat_cap_max_links,
    )
    new_markdown, applied_count, applied_suggestions = apply_suggestions_to_markdown(
        instance.body_markdown,
        suggestions,
        max_apply=budget,
    )
    if applied_count == 0 or new_markdown == instance.body_markdown:
        return 0

    instance.body_markdown = new_markdown
    instance._seo_skip_signal = True
    instance.save()
    instance._seo_skip_signal = False
    if hasattr(instance, "record_revision"):
        instance.record_revision(note=f"SEO interlink auto-update: {applied_count} links applied")

    anchors = {row["anchor_text"] for row in applied_suggestions}
    SeoSuggestion.objects.filter(
        content_type=adapter.content_type,
        object_id=adapter.pk,
        suggestion_type=SeoSuggestion.SuggestionType.INTERLINK,
        status=SeoSuggestion.Status.PENDING,
        payload_json__anchor_text__in=list(anchors),
    ).update(
        status=SeoSuggestion.Status.APPLIED,
        applied_at=timezone.now(),
    )
    SeoLinkEdge.objects.filter(
        source_content_type=adapter.content_type,
        source_object_id=adapter.pk,
        anchor_text__in=list(anchors),
        status=SeoLinkEdge.Status.SUGGESTED,
    ).update(status=SeoLinkEdge.Status.APPLIED)
    return applied_count


def _apply_interlink_payload(target, payload):
    suggestion = {
        "anchor_text": payload.get("anchor_text", ""),
        "target_url": payload.get("target_url", ""),
        "score": payload.get("score", 0.0),
    }
    markdown, applied_count, _ = apply_suggestions_to_markdown(
        target.body_markdown or "",
        [suggestion],
        max_apply=1,
    )
    if applied_count == 0:
        return 0
    target.body_markdown = markdown
    target._seo_skip_signal = True
    target.save(update_fields=["body_markdown", "updated_at"])
    target._seo_skip_signal = False
    if hasattr(target, "record_revision"):
        target.record_revision(note="SEO interlink suggestion applied")
    return applied_count


def audit_instance(instance, *, trigger="save", request=None):
    if not instance or not instance.pk:
        return None
    settings = SeoEngineSettings.get_solo()
    if not settings.enable_checks:
        return None

    adapter = _build_adapter_from_instance(instance)
    metadata = resolve_metadata(adapter, request=request).to_dict()

    results = run_checks(
        adapter,
        metadata,
        min_internal_links=settings.min_links_per_doc,
    )
    counters = _score_from_results(results)
    checksum = _checksum(adapter, metadata, results)

    snapshot = SeoAuditSnapshot.objects.create(
        content_type=adapter.content_type,
        object_id=adapter.pk,
        url=adapter.url,
        route_type=adapter.route_type,
        score=counters["score"],
        critical_count=counters["critical_count"],
        warning_count=counters["warning_count"],
        passed_count=counters["passed_count"],
        failed_count=counters["failed_count"],
        trigger=trigger,
        metadata_json=metadata,
        checksum=checksum,
    )

    issue_rows = []
    for result in results:
        if result.passed:
            continue
        issue_rows.append(
            SeoIssue(
                snapshot=snapshot,
                check_key=result.key,
                severity=result.severity,
                status=SeoIssue.Status.OPEN,
                message=result.message,
                suggested_fix=result.suggested_fix,
                autofixable=result.autofixable,
                details_json=result.details,
            )
        )
    if issue_rows:
        SeoIssue.objects.bulk_create(issue_rows)

    # Rebuild pending suggestions.
    SeoSuggestion.objects.filter(
        content_type=adapter.content_type,
        object_id=adapter.pk,
        status=SeoSuggestion.Status.PENDING,
    ).delete()
    SeoLinkEdge.objects.filter(
        source_content_type=adapter.content_type,
        source_object_id=adapter.pk,
        status=SeoLinkEdge.Status.SUGGESTED,
    ).delete()

    if any(not row.passed and row.autofixable for row in results):
        _build_metadata_suggestion(adapter, metadata)

    target_pool = _target_pool(adapter)
    budget = compute_link_budget(
        total_docs=max(Post.objects.published().count() + Page.objects.published().count(), 1),
        word_count=adapter.word_count,
        min_links=settings.min_links_per_doc,
        whitehat_cap=settings.whitehat_cap_max_links,
    )
    interlink_suggestions = build_interlink_suggestions(
        adapter,
        target_pool,
        max_links=budget,
        min_score=settings.link_suggestion_min_score,
    )
    _persist_interlink_suggestions(adapter, interlink_suggestions)
    try:
        _apply_interlinks(adapter, interlink_suggestions, settings)
    except Exception:
        # Preserve audit snapshot even if link auto-application fails.
        logger.warning("Auto-interlink application failed for %s pk=%s", adapter.route_type, adapter.pk, exc_info=True)

    return snapshot


def audit_content(content_type: str, object_id: int, *, trigger="manual"):
    instance = _get_instance(content_type, object_id)
    if not instance:
        return None
    return audit_instance(instance, trigger=trigger)


def audit_content_batch(
    content_type: str,
    object_ids,
    *,
    trigger: str = "save",
    run_autopilot: bool = True,
):
    """
    Audit a batch of content ids and optionally run autopilot per object.
    """
    normalized = (content_type or "").strip().lower()
    if normalized not in {"post", "page"}:
        return {"processed": 0, "snapshots": 0, "autopilot_approved": 0}

    processed = 0
    snapshots = 0
    autopilot_approved = 0
    unique_ids = []
    seen = set()
    for raw_id in object_ids or []:
        try:
            value = int(raw_id)
        except (TypeError, ValueError):
            continue
        if value in seen:
            continue
        seen.add(value)
        unique_ids.append(value)

    for object_id in unique_ids:
        instance = _get_instance(normalized, object_id)
        if not instance:
            continue
        processed += 1
        snapshot = audit_instance(instance, trigger=trigger)
        if snapshot:
            snapshots += 1
        if run_autopilot:
            result = run_autopilot_for_instance(instance)
            autopilot_approved += int(result.get("approved") or 0)

    return {
        "processed": processed,
        "snapshots": snapshots,
        "autopilot_approved": autopilot_approved,
    }


def live_check(content_type: str, payload: dict):
    model = Post if content_type == "post" else Page
    ct = ContentType.objects.get_for_model(model)
    title = (payload.get("title") or "").strip()
    meta_title = (payload.get("meta_title") or "").strip()
    meta_description = (payload.get("meta_description") or "").strip()
    body_markdown = payload.get("body_markdown") or ""
    canonical_url = payload.get("canonical_url") or ""
    slug = payload.get("slug") or ""
    summary = payload.get("summary") or ""
    excerpt = payload.get("excerpt") or ""

    adapter = ContentAdapter(
        pk=0,
        model=model,
        content_type=ct,
        route_type=content_type,
        title=title,
        slug=slug,
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        body_markdown=body_markdown,
        body_html="",
        word_count=len((body_markdown or "").split()),
        created_at=timezone.now(),
        updated_at=timezone.now(),
        published_at=None,
        url="/",
        summary=summary,
        excerpt=excerpt,
        og_image_url="",
        is_featured=False,
        status="draft",
    )
    metadata = resolve_metadata(adapter).to_dict()
    settings = SeoEngineSettings.get_solo()
    results = run_checks(adapter, metadata, min_internal_links=settings.min_links_per_doc)
    counters = _score_from_results(results)
    return {
        "score": counters["score"],
        "critical_count": counters["critical_count"],
        "warning_count": counters["warning_count"],
        "results": [_serialize_check_result(row) for row in results],
        "metadata": metadata,
    }


def apply_due_autofixes():
    settings = SeoEngineSettings.get_solo()
    if not settings.auto_fix_enabled:
        return {"updated": 0, "reason": "disabled"}
    cutoff = timezone.now() - timedelta(hours=max(settings.auto_fix_after_hours, 1))
    pending_due = SeoSuggestion.objects.filter(
        suggestion_type=SeoSuggestion.SuggestionType.METADATA,
        status__in=[SeoSuggestion.Status.PENDING, SeoSuggestion.Status.NEEDS_CORRECTION],
        created_at__lte=cutoff,
    ).count()
    # Approval-first policy: scheduled tasks only surface due suggestions, never auto-apply.
    return {"updated": 0, "pending_due": pending_due, "reason": "approval_required"}


def run_autopilot_for_instance(
    instance,
    *,
    reviewer=None,
    min_confidence: float | None = None,
    limit: int = 120,
):
    """
    Auto-approve safe suggestions for a single content instance.
    """
    if not instance or not getattr(instance, "pk", None):
        return {"ok": False, "reason": "missing_instance", "approved": 0, "skipped": 0}

    settings = SeoEngineSettings.get_solo()
    if not settings.auto_fix_enabled:
        return {"ok": False, "reason": "autopilot_disabled", "approved": 0, "skipped": 0}

    threshold = (
        settings.autopilot_min_confidence if min_confidence is None else float(min_confidence)
    )
    threshold = max(min(threshold, 1.0), 0.0)
    safe_limit = max(int(limit or 0), 1)

    content_type = ContentType.objects.get_for_model(instance.__class__)
    candidates = list(
        SeoSuggestion.objects.filter(
            content_type=content_type,
            object_id=instance.pk,
            status__in=[SeoSuggestion.Status.PENDING, SeoSuggestion.Status.NEEDS_CORRECTION],
            suggestion_type__in=[
                SeoSuggestion.SuggestionType.METADATA,
                SeoSuggestion.SuggestionType.INTERLINK,
            ],
            confidence__gte=threshold,
        )
        .order_by("-confidence", "created_at")[:safe_limit]
    )

    approved = 0
    skipped = 0
    for suggestion in candidates:
        result = approve_suggestion(suggestion.id, reviewer=reviewer)
        if result.get("ok"):
            approved += 1
        else:
            skipped += 1

    return {
        "ok": True,
        "approved": approved,
        "skipped": skipped,
        "considered": len(candidates),
        "threshold": threshold,
    }


def handle_deleted_content(instance):
    if not instance:
        return None
    old_path = ""
    try:
        old_path = instance.get_absolute_url()
    except Exception:
        pass
    if not old_path:
        return None
    old_path = old_path if old_path.startswith("/") else f"/{old_path}"

    ct = ContentType.objects.get_for_model(instance.__class__)
    SeoSuggestion.objects.create(
        content_type=ct,
        object_id=getattr(instance, "pk", 0) or 0,
        suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
        payload_json={
            "old_path": old_path,
            "suggested_target": "/",
            "status_code": 301,
        },
        confidence=0.5,
        status=SeoSuggestion.Status.PENDING,
    )
    SeoRedirectRule.objects.get_or_create(
        old_path=old_path,
        defaults={
            "target_url": "",
            "status_code": SeoRedirectRule.StatusCode.GONE,
            "is_active": True,
            "source_model": f"{instance._meta.app_label}.{instance._meta.model_name}",
            "source_object_id": getattr(instance, "pk", None),
            "notes": "Auto-created on content deletion.",
        },
    )
    return old_path


def disable_gone_redirect_for_live_instance(instance):
    if not instance:
        return 0

    path = ""
    try:
        path = instance.get_absolute_url()
    except Exception:
        return 0

    if not path:
        return 0
    path = path if path.startswith("/") else f"/{path}"

    return SeoRedirectRule.objects.filter(
        old_path=path,
        is_active=True,
        status_code=SeoRedirectRule.StatusCode.GONE,
    ).update(
        is_active=False,
        notes="Auto-disabled because content path is live.",
    )


def approve_suggestion(candidate_id: int, *, reviewer=None):
    suggestion = SeoSuggestion.objects.select_related("content_type").filter(pk=candidate_id).first()
    if not suggestion:
        return {"ok": False, "message": "Suggestion not found.", "status": 404}
    if suggestion.status not in {
        SeoSuggestion.Status.PENDING,
        SeoSuggestion.Status.NEEDS_CORRECTION,
    }:
        return {"ok": False, "message": "Suggestion is not approvable.", "status": 409}

    model = suggestion.content_type.model_class()
    target = model.objects.filter(pk=suggestion.object_id).first() if model else None
    payload = suggestion.payload_json or {}
    now = timezone.now()

    if suggestion.suggestion_type == SeoSuggestion.SuggestionType.METADATA:
        if not target:
            return {"ok": False, "message": "Target content not found.", "status": 404}
        lock = _metadata_lock_for_target(suggestion.content_type, suggestion.object_id)
        changed = _apply_metadata_payload(target, payload, lock)
        suggestion.status = SeoSuggestion.Status.APPLIED
        suggestion.applied_at = now
        suggestion.save(update_fields=["status", "applied_at"])
        return {
            "ok": True,
            "message": "Metadata suggestion approved.",
            "changed_fields": changed,
            "target_url": target.get_absolute_url(),
        }

    if suggestion.suggestion_type == SeoSuggestion.SuggestionType.INTERLINK:
        if not target:
            return {"ok": False, "message": "Target content not found.", "status": 404}
        applied_count = _apply_interlink_payload(target, payload)
        if applied_count == 0:
            return {"ok": False, "message": "Anchor not found in body text.", "status": 409}
        suggestion.status = SeoSuggestion.Status.APPLIED
        suggestion.applied_at = now
        suggestion.save(update_fields=["status", "applied_at"])
        return {
            "ok": True,
            "message": "Interlink suggestion approved.",
            "applied_count": applied_count,
            "target_url": target.get_absolute_url(),
        }

    if suggestion.suggestion_type == SeoSuggestion.SuggestionType.REDIRECT:
        old_path = payload.get("old_path", "")
        target_url = payload.get("suggested_target", "/")
        if not old_path:
            return {"ok": False, "message": "Redirect payload is incomplete.", "status": 409}
        status_code = int(payload.get("status_code", 301))
        if status_code not in {301, 302, 410}:
            status_code = 301
        rule, _ = SeoRedirectRule.objects.update_or_create(
            old_path=old_path,
            defaults={
                "target_url": target_url if status_code != 410 else "",
                "status_code": status_code,
                "is_active": True,
                "notes": "Approved from SEO suggestion queue.",
                "created_by": reviewer if getattr(reviewer, "is_authenticated", False) else None,
            },
        )
        suggestion.status = SeoSuggestion.Status.APPLIED
        suggestion.applied_at = now
        suggestion.save(update_fields=["status", "applied_at"])
        return {
            "ok": True,
            "message": "Redirect suggestion approved.",
            "redirect_rule_id": rule.id,
        }

    return {"ok": False, "message": "Unsupported suggestion type.", "status": 409}


def reject_suggestion(candidate_id: int):
    suggestion = SeoSuggestion.objects.filter(pk=candidate_id).first()
    if not suggestion:
        return {"ok": False, "message": "Suggestion not found.", "status": 404}
    if suggestion.status not in {
        SeoSuggestion.Status.PENDING,
        SeoSuggestion.Status.NEEDS_CORRECTION,
    }:
        return {"ok": False, "message": "Suggestion is not rejectable.", "status": 409}
    suggestion.status = SeoSuggestion.Status.REJECTED
    suggestion.save(update_fields=["status"])
    return {"ok": True, "message": "Suggestion rejected."}


def seo_overview_metrics():
    latest_snapshot = SeoAuditSnapshot.objects.order_by("-audited_at").first()
    issue_counts = {
        "critical_open": SeoIssue.objects.filter(
            status=SeoIssue.Status.OPEN,
            severity=SeoIssue.Severity.CRITICAL,
        ).count(),
        "warning_open": SeoIssue.objects.filter(
            status=SeoIssue.Status.OPEN,
            severity=SeoIssue.Severity.WARNING,
        ).count(),
    }
    suggestion_counts = {
        "pending_total": SeoSuggestion.objects.filter(status=SeoSuggestion.Status.PENDING).count(),
        "pending_metadata": SeoSuggestion.objects.filter(
            status=SeoSuggestion.Status.PENDING,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
        ).count(),
        "pending_interlinks": SeoSuggestion.objects.filter(
            status=SeoSuggestion.Status.PENDING,
            suggestion_type=SeoSuggestion.SuggestionType.INTERLINK,
        ).count(),
        "pending_redirects": SeoSuggestion.objects.filter(
            status=SeoSuggestion.Status.PENDING,
            suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
        ).count(),
    }
    route_breakdown = list(
        SeoAuditSnapshot.objects.values("route_type")
        .annotate(total=Count("id"), avg_score=Avg("score"))
        .order_by("route_type")
    )
    return {
        "latest_score": latest_snapshot.score if latest_snapshot else None,
        "latest_audited_at": latest_snapshot.audited_at if latest_snapshot else None,
        "issue_counts": issue_counts,
        "suggestion_counts": suggestion_counts,
        "route_breakdown": route_breakdown,
    }
