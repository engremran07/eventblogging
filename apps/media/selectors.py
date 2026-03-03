from __future__ import annotations

import uuid

from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404

from .models import FileType, MediaFile


def get_media_file(*, pk: uuid.UUID) -> MediaFile:
    """Return a single active media file or raise 404."""
    return get_object_or_404(
        MediaFile.objects.select_related("uploaded_by"),
        pk=pk,
        is_active=True,
    )


def get_media_list(
    *,
    search: str = "",
    file_type: str = "",
    folder: str = "",
    sort_by: str = "-created_at",
) -> QuerySet[MediaFile]:
    """Return a filtered, ordered queryset of active media files."""
    qs = MediaFile.objects.filter(is_active=True).select_related("uploaded_by")

    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(original_filename__icontains=search)
        )

    if file_type:
        qs = qs.filter(file_type=file_type)

    if folder:
        qs = qs.filter(folder=folder)

    allowed_sorts = {
        "-created_at",
        "created_at",
        "-file_size",
        "file_size",
        "title",
        "-title",
        "original_filename",
        "-original_filename",
    }
    if sort_by not in allowed_sorts:
        sort_by = "-created_at"

    return qs.order_by(sort_by)


def get_media_stats() -> dict[str, int]:
    """Return aggregate counts of active media files by type."""
    qs = MediaFile.objects.filter(is_active=True)
    counts = (
        qs.values("file_type")
        .annotate(count=Count("id"))
        .order_by("file_type")
    )
    stats: dict[str, int] = {
        "total": 0,
        FileType.IMAGE.value: 0,
        FileType.DOCUMENT.value: 0,
        FileType.VIDEO.value: 0,
        FileType.AUDIO.value: 0,
        FileType.OTHER.value: 0,
    }
    for row in counts:
        ft = row["file_type"]
        c = row["count"]
        stats[ft] = c
        stats["total"] += c
    return stats


def get_folder_list() -> list[str]:
    """Return a sorted list of distinct non-empty folder values."""
    return sorted(
        MediaFile.objects.filter(is_active=True)
        .exclude(folder="")
        .values_list("folder", flat=True)
        .distinct()
    )
