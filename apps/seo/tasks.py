from __future__ import annotations

from celery import shared_task

from blog.models import Post
from pages.models import Page

from .admin_config_services import create_scan_job, enqueue_scan_job, run_scan_job
from .models import SeoScanJob
from .services import apply_due_autofixes, audit_content


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
    batch_size = max(min(int(batch_size), 500), 1)
    cursor = max(int(cursor), 0)

    post_ids = list(Post.objects.order_by("id").values_list("id", flat=True)[cursor : cursor + batch_size])
    if post_ids:
        for post_id in post_ids:
            audit_content("post", post_id, trigger="scheduled")
        next_cursor = cursor + len(post_ids)
        return {"ok": True, "kind": "post", "processed": len(post_ids), "next_cursor": next_cursor}

    page_cursor = cursor - Post.objects.count()
    if page_cursor < 0:
        page_cursor = 0
    page_ids = list(
        Page.objects.order_by("id").values_list("id", flat=True)[page_cursor : page_cursor + batch_size]
    )
    for page_id in page_ids:
        audit_content("page", page_id, trigger="scheduled")
    done = len(page_ids) < batch_size
    return {
        "ok": True,
        "kind": "page",
        "processed": len(page_ids),
        "next_cursor": cursor + len(page_ids),
        "done": done,
    }


@shared_task(bind=True, ignore_result=False)
def seo_run_scan_job(self, job_id: int):
    return run_scan_job(job_id)


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
