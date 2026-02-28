"""
SEO app database query selectors.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import (
    SeoAuditSnapshot,
    SeoIssue,
    SeoLinkEdge,
    SeoMetadataLock,
    SeoRedirectRule,
    SeoRouteProfile,
    SeoScanJob,
    SeoScanJobItem,
    SeoSuggestion,
    TaxonomySynonymGroup,
)


def get_seo_route_profile(route_name: str) -> SeoRouteProfile | None:
    try:
        return SeoRouteProfile.objects.get(route_name=route_name)
    except SeoRouteProfile.DoesNotExist:
        return None


def get_all_seo_route_profiles() -> QuerySet[SeoRouteProfile]:
    return SeoRouteProfile.objects.order_by("route_name")


def get_latest_seo_snapshot(obj_type: str, obj_id: int) -> SeoAuditSnapshot | None:
    return (
        SeoAuditSnapshot.objects.filter(
            content_type__model=obj_type,
            object_id=obj_id,
        )
        .order_by("-audited_at")
        .first()
    )


def get_seo_snapshots(obj_type: str, obj_id: int) -> QuerySet[SeoAuditSnapshot]:
    return SeoAuditSnapshot.objects.filter(
        content_type__model=obj_type,
        object_id=obj_id,
    ).order_by("-audited_at")


def get_seo_issues(
    obj_type: str | None = None,
    obj_id: int | None = None,
    severity: str | None = None,
) -> QuerySet[SeoIssue]:
    issues = SeoIssue.objects.select_related("snapshot")

    if obj_type:
        issues = issues.filter(snapshot__content_type__model=obj_type)
    if obj_id is not None:
        issues = issues.filter(snapshot__object_id=obj_id)
    if severity:
        issues = issues.filter(severity=severity)

    return issues.order_by("severity", "-created_at")


def get_object_seo_issues(obj_type: str, obj_id: int) -> QuerySet[SeoIssue]:
    return get_seo_issues(obj_type=obj_type, obj_id=obj_id)


def get_seo_suggestions(status: str | None = None) -> QuerySet[SeoSuggestion]:
    suggestions = SeoSuggestion.objects.select_related("content_type")
    if status:
        suggestions = suggestions.filter(status=status)
    return suggestions.order_by("-created_at")


def get_pending_seo_suggestions() -> QuerySet[SeoSuggestion]:
    return get_seo_suggestions(status=SeoSuggestion.Status.PENDING)


def get_approved_seo_suggestions() -> QuerySet[SeoSuggestion]:
    return get_seo_suggestions(status=SeoSuggestion.Status.APPLIED)


def get_object_seo_suggestions(obj_type: str, obj_id: int) -> QuerySet[SeoSuggestion]:
    return SeoSuggestion.objects.filter(
        content_type__model=obj_type,
        object_id=obj_id,
    ).order_by("-created_at")


def get_redirect_rule(source_path: str) -> SeoRedirectRule | None:
    try:
        return SeoRedirectRule.objects.get(old_path=source_path)
    except SeoRedirectRule.DoesNotExist:
        return None


def get_active_redirect_rules() -> QuerySet[SeoRedirectRule]:
    return SeoRedirectRule.objects.filter(is_active=True).order_by("old_path")


def get_broken_redirect_rules() -> QuerySet[SeoRedirectRule]:
    return SeoRedirectRule.objects.filter(
        is_active=True,
        target_url="",
        status_code=SeoRedirectRule.StatusCode.MOVED_PERMANENTLY,
    ).order_by("-updated_at")


def get_link_edges(
    from_type: str | None = None,
    to_type: str | None = None,
) -> QuerySet[SeoLinkEdge]:
    edges = SeoLinkEdge.objects.select_related("source_content_type", "target_content_type")

    if from_type:
        edges = edges.filter(source_content_type__model=from_type)
    if to_type:
        edges = edges.filter(target_content_type__model=to_type)

    return edges


def get_object_inbound_links(obj_type: str, obj_id: int) -> QuerySet[SeoLinkEdge]:
    return SeoLinkEdge.objects.filter(
        target_content_type__model=obj_type,
        target_object_id=obj_id,
    ).select_related("source_content_type")


def get_object_outbound_links(obj_type: str, obj_id: int) -> QuerySet[SeoLinkEdge]:
    return SeoLinkEdge.objects.filter(
        source_content_type__model=obj_type,
        source_object_id=obj_id,
    ).select_related("target_content_type")


def get_metadata_lock(obj_type: str, obj_id: int) -> SeoMetadataLock | None:
    try:
        return SeoMetadataLock.objects.select_related("content_type").get(
            content_type__model=obj_type,
            object_id=obj_id,
        )
    except SeoMetadataLock.DoesNotExist:
        return None


def get_locked_objects() -> QuerySet[SeoMetadataLock]:
    return SeoMetadataLock.objects.select_related("content_type").order_by("-updated_at")


def get_latest_scan_job() -> SeoScanJob | None:
    return SeoScanJob.objects.order_by("-created_at").first()


def get_scan_jobs(status: str | None = None) -> QuerySet[SeoScanJob]:
    jobs = SeoScanJob.objects.prefetch_related("items")
    if status:
        jobs = jobs.filter(status=status)
    return jobs.order_by("-created_at")


def get_scan_job_items(job: SeoScanJob) -> QuerySet[SeoScanJobItem]:
    return SeoScanJobItem.objects.filter(job=job).order_by("created_at", "id")


def get_synonym_groups() -> QuerySet[TaxonomySynonymGroup]:
    return TaxonomySynonymGroup.objects.prefetch_related("terms").order_by("name")


def get_synonym_group(group_id: int) -> TaxonomySynonymGroup | None:
    try:
        return TaxonomySynonymGroup.objects.prefetch_related("terms").get(id=group_id)
    except TaxonomySynonymGroup.DoesNotExist:
        return None


def find_synonyms(term: str) -> list[str]:
    normalized = (term or "").strip().lower()
    if not normalized:
        return []

    group = (
        TaxonomySynonymGroup.objects.filter(
            Q(name__icontains=normalized) | Q(terms__normalized_term=normalized)
        )
        .prefetch_related("terms")
        .distinct()
        .first()
    )
    if not group:
        return [term]

    terms = [
        row.term
        for row in group.terms.filter(is_active=True).order_by("-is_canonical", "term")
    ]
    return terms or [term]
