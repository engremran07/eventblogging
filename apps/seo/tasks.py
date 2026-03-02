from __future__ import annotations

import logging

from celery import shared_task

from blog.models import Post
from pages.models import Page

from .admin_config_services import create_scan_job, enqueue_scan_job, run_scan_job
from .models import SeoScanJob
from .services import (
    apply_due_autofixes,
    audit_content,
    audit_instance,
    compute_content_signals,
    compute_tfidf_signals,
    write_back_audit_score,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=False)
def seo_index_post(self, post_id: int):
    snapshot = audit_content("post", post_id, trigger="scheduled")
    if snapshot is None:
        return {"ok": False, "reason": "missing_post", "post_id": post_id}
    return {"ok": True, "snapshot_id": snapshot.id, "score": snapshot.score}


@shared_task(bind=True, ignore_result=False)
def seo_index_page(self, page_id: int):
    snapshot = audit_content("page", page_id, trigger="scheduled")
    if snapshot is None:
        return {"ok": False, "reason": "missing_page", "page_id": page_id}
    return {"ok": True, "snapshot_id": snapshot.id, "score": snapshot.score}


@shared_task(bind=True, ignore_result=False)
def seo_apply_due_autofixes(self):
    return apply_due_autofixes()


@shared_task(bind=True, ignore_result=False)
def seo_backfill(self, batch_size: int = 50, cursor: int = 0):
    """Run the full SEO signal pipeline in batches across all posts then pages."""
    from .interlink import reverse_interlink_scan
    from .signals import _apply_auto_seo_enhancements, _apply_page_metadata

    batch_size = max(min(int(batch_size), 500), 1)
    cursor = max(int(cursor), 0)

    post_count = Post.objects.count()

    # Phase 1: Process posts
    if cursor < post_count:
        post_ids = list(
            Post.objects.order_by("id").values_list("id", flat=True)[cursor : cursor + batch_size]
        )
        processed = 0
        errors = 0
        for post_id in post_ids:
            try:
                post = Post.objects.get(pk=post_id)
                _apply_auto_seo_enhancements(post)
                snapshot = audit_instance(post, trigger="backfill")
                compute_content_signals(post)
                compute_tfidf_signals(post)
                if snapshot:
                    write_back_audit_score(post, snapshot)
                if post.status == Post.Status.PUBLISHED:
                    reverse_interlink_scan(post)
                processed += 1
            except Exception:
                errors += 1
                logger.exception("SEO backfill failed for Post id=%s", post_id)
        next_cursor = cursor + len(post_ids)
        return {
            "ok": True,
            "kind": "post",
            "processed": processed,
            "errors": errors,
            "next_cursor": next_cursor,
            "done": False,
        }

    # Phase 2: Process pages
    page_cursor = cursor - post_count
    if page_cursor < 0:
        page_cursor = 0
    page_ids = list(
        Page.objects.order_by("id").values_list("id", flat=True)[page_cursor : page_cursor + batch_size]
    )
    processed = 0
    errors = 0
    for page_id in page_ids:
        try:
            page = Page.objects.get(pk=page_id)
            _apply_page_metadata(page)
            snapshot = audit_instance(page, trigger="backfill")
            compute_content_signals(page)
            if snapshot:
                write_back_audit_score(page, snapshot)
            if getattr(page, "status", "") == "published":
                reverse_interlink_scan(page)
            processed += 1
        except Exception:
            errors += 1
            logger.exception("SEO backfill failed for Page id=%s", page_id)
    done = len(page_ids) < batch_size
    return {
        "ok": True,
        "kind": "page",
        "processed": processed,
        "errors": errors,
        "next_cursor": cursor + len(page_ids),
        "done": done,
    }


@shared_task(bind=True, ignore_result=False)
def seo_run_scan_job(self, job_id: int):
    return run_scan_job(job_id)


@shared_task(bind=True, ignore_result=False)
def seo_repair_orphans(self):
    """Find content with no inbound interlinks and create link suggestions."""
    from .interlink import repair_orphans

    result = repair_orphans()
    return {"ok": True, **result}


@shared_task(bind=True, ignore_result=False)
def seo_verify_graph_connectivity(self):
    """Check the interlink graph for connectivity gaps."""
    from .interlink import verify_graph_connectivity

    result = verify_graph_connectivity()
    return {"ok": True, **result}


@shared_task(bind=True, ignore_result=False)
def seo_schedule_full_scan(self):
    if SeoScanJob.objects.filter(status__in=[SeoScanJob.Status.QUEUED, SeoScanJob.Status.RUNNING]).exists():
        return {"ok": False, "reason": "scan_already_running"}
    job = create_scan_job(
        job_type=SeoScanJob.JobType.FULL,
        started_by=None,
        trigger=SeoScanJob.Trigger.SCHEDULED,
        notes="Scheduled full-site SEO scan.",
    )
    enqueue_scan_job(job.id)
    return {"ok": True, "job_id": job.id}
