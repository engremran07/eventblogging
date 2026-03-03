from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from django.conf import settings
from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404

from .models import FileType, MediaFile

logger = logging.getLogger(__name__)


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
    path: str = "",
    sort_by: str = "-created_at",
) -> QuerySet[MediaFile]:
    """
    Return a filtered, ordered queryset of active media files.

    ``folder`` filters for an exact folder match (backward compat).
    ``path`` filters for files *inside* a folder tree (folder starts with path).
    """
    qs = MediaFile.objects.filter(is_active=True).select_related("uploaded_by")

    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(original_filename__icontains=search)
        )

    if file_type:
        qs = qs.filter(file_type=file_type)

    if path:
        # Show files whose folder exactly matches the path (direct children)
        qs = qs.filter(folder=path)
    elif folder:
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


# ── Folder tree from disk + DB ──────────────────────────────────────────────


def _count_files_by_folder() -> dict[str, int]:
    """Return {folder_path: file_count} from active MediaFile records."""
    rows = (
        MediaFile.objects.filter(is_active=True)
        .exclude(folder="")
        .values("folder")
        .annotate(cnt=Count("id"))
    )
    return {row["folder"]: row["cnt"] for row in rows}


def _post_by_folder() -> dict[str, dict[str, Any]]:
    """Return {folder_path: {id, title, slug}} for post-linked folders."""
    from blog.models import Post

    result: dict[str, dict[str, Any]] = {}
    for post in Post.objects.only("id", "title", "slug").prefetch_related("categories"):
        try:
            from media.services import generate_post_media_folder

            folder = generate_post_media_folder(post)
            result[folder] = {
                "id": post.pk,
                "title": str(post.title),
                "slug": str(post.slug),
            }
        except Exception:
            logger.warning("Failed to generate folder for post pk=%s", post.pk, exc_info=True)
    return result


def get_folder_tree() -> list[dict[str, Any]]:
    """
    Build a hierarchical folder tree from the physical ``media/`` directory.

    Each node: ``{name, path, children, file_count, post}``
    Only includes directories under ``media/posts/`` (the managed area).
    """
    media_root = str(settings.MEDIA_ROOT)
    posts_root = os.path.join(media_root, "posts")

    if not os.path.isdir(posts_root):
        return []

    file_counts = _count_files_by_folder()
    post_map = _post_by_folder()

    def _build_node(abs_path: str, rel_path: str) -> dict[str, Any]:
        name = os.path.basename(abs_path)
        children: list[dict[str, Any]] = []

        try:
            entries = sorted(os.listdir(abs_path))
        except OSError:
            entries = []

        for entry in entries:
            child_abs = os.path.join(abs_path, entry)
            if os.path.isdir(child_abs):
                child_rel = f"{rel_path}/{entry}" if rel_path else entry
                children.append(_build_node(child_abs, child_rel))

        # Count files in this folder and all descendant folders
        direct_count = file_counts.get(rel_path, 0)
        total_count = direct_count + sum(c.get("total_file_count", 0) for c in children)

        return {
            "name": name,
            "path": rel_path,
            "children": children,
            "file_count": direct_count,
            "total_file_count": total_count,
            "post": post_map.get(rel_path),
            "has_children": bool(children),
        }

    # Build the tree starting from media/posts/
    root_children: list[dict[str, Any]] = []
    try:
        top_entries = sorted(os.listdir(posts_root))
    except OSError:
        top_entries = []

    for entry in top_entries:
        entry_abs = os.path.join(posts_root, entry)
        if os.path.isdir(entry_abs):
            root_children.append(_build_node(entry_abs, f"posts/{entry}"))

    return root_children


def get_breadcrumbs(path: str) -> list[dict[str, str]]:
    """
    Build breadcrumb trail from a folder path.

    Example: ``posts/technology/frontend`` → [
        {name: "posts", path: "posts"},
        {name: "technology", path: "posts/technology"},
        {name: "frontend", path: "posts/technology/frontend"},
    ]
    """
    if not path:
        return []

    parts = path.strip("/").split("/")
    crumbs: list[dict[str, str]] = []
    for i, part in enumerate(parts):
        crumbs.append({
            "name": part,
            "path": "/".join(parts[: i + 1]),
        })
    return crumbs


def get_children_of_path(path: str) -> list[dict[str, Any]]:
    """
    Return immediate child folders of a given path, with file counts and post linkage.
    """
    media_root = str(settings.MEDIA_ROOT)
    target_dir = os.path.join(media_root, path) if path else os.path.join(media_root, "posts")

    if not os.path.isdir(target_dir):
        return []

    file_counts = _count_files_by_folder()
    post_map = _post_by_folder()

    children: list[dict[str, Any]] = []
    try:
        entries = sorted(os.listdir(target_dir))
    except OSError:
        return []

    for entry in entries:
        child_abs = os.path.join(target_dir, entry)
        if os.path.isdir(child_abs):
            child_rel = f"{path}/{entry}" if path else f"posts/{entry}"
            children.append({
                "name": entry,
                "path": child_rel,
                "file_count": file_counts.get(child_rel, 0),
                "post": post_map.get(child_rel),
                "has_children": any(
                    os.path.isdir(os.path.join(child_abs, e))
                    for e in os.listdir(child_abs)
                ) if os.path.isdir(child_abs) else False,
            })

    return children
