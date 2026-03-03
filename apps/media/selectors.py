from __future__ import annotations

import logging
import uuid
from typing import Any

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


# ── Folder tree from DB ──────────────────────────────────────────────────────


def _count_files_by_folder() -> dict[str, int]:
    """Return {folder_path: file_count} from active MediaFile records."""
    rows = (
        MediaFile.objects.filter(is_active=True)
        .exclude(folder="")
        .values("folder")
        .annotate(cnt=Count("id"))
    )
    return {row["folder"]: row["cnt"] for row in rows}


def _content_by_folder(folder_paths: set[str]) -> dict[str, dict[str, Any]]:
    """
    Return {folder_path: {id, title, slug, type}} for content-linked folders.

    Maps both blog posts (``posts/…``) and pages (``pages/…``).
    Only maps folders present in *folder_paths* to avoid querying all records.
    """
    from blog.models import Post
    from pages.models import Page

    result: dict[str, dict[str, Any]] = {}
    if not folder_paths:
        return result

    # Map posts
    for post in Post.objects.only("id", "title", "slug").prefetch_related("categories"):
        try:
            from media.services import generate_post_media_folder

            folder = generate_post_media_folder(post)
            if folder in folder_paths:
                result[folder] = {
                    "id": post.pk,
                    "title": str(post.title),
                    "slug": str(post.slug),
                    "type": "post",
                }
        except Exception:
            logger.warning(
                "Failed to generate folder for post pk=%s", post.pk, exc_info=True
            )

    # Map pages
    for page in Page.objects.only("id", "title", "slug"):
        try:
            from media.services import generate_page_media_folder

            folder = generate_page_media_folder(page)
            if folder in folder_paths:
                result[folder] = {
                    "id": page.pk,
                    "title": str(page.title),
                    "slug": str(page.slug),
                    "type": "page",
                }
        except Exception:
            logger.warning(
                "Failed to generate folder for page pk=%s", page.pk, exc_info=True
            )

    return result


def _ancestor_paths(folder: str) -> list[str]:
    """
    Return all ancestor path segments for a folder path.

    Example: ``posts/tech/frontend/my-post`` →
        [``posts``, ``posts/tech``, ``posts/tech/frontend``]
    """
    parts = folder.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts) - 1)]


def get_folder_tree() -> list[dict[str, Any]]:
    """
    Build a hierarchical folder tree from **DB records only**.

    Only folders that contain active media files (or have descendants that do)
    appear in the tree.  Empty physical directories are hidden.

    Each node: ``{name, path, children, file_count, total_file_count, post,
    has_children}``
    """
    file_counts = _count_files_by_folder()
    if not file_counts:
        return []

    # Collect every folder path that should appear in the tree:
    # - leaf folders with actual files
    # - all ancestor segments (so the hierarchy is navigable)
    all_paths: set[str] = set()
    for folder_path in file_counts:
        all_paths.add(folder_path)
        all_paths.update(_ancestor_paths(folder_path))

    content_map = _content_by_folder(all_paths)

    # Build an intermediate nested dict → then convert to node list
    tree: dict[str, Any] = {}
    for path in all_paths:
        parts = path.split("/")
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]

    def _to_nodes(subtree: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for name in sorted(subtree.keys()):
            path = f"{prefix}/{name}" if prefix else name
            children = _to_nodes(subtree[name], path)
            direct_count = file_counts.get(path, 0)
            total_count = direct_count + sum(
                c["total_file_count"] for c in children
            )
            nodes.append({
                "name": name,
                "path": path,
                "children": children,
                "file_count": direct_count,
                "total_file_count": total_count,
                "content": content_map.get(path),
                "has_children": bool(children),
            })
        return nodes

    return _to_nodes(tree, "")


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
    Return immediate child folder segments of *path* that contain media
    (directly or in any descendant).

    Built entirely from DB records — empty physical directories are hidden.
    """
    file_counts = _count_files_by_folder()
    if not file_counts:
        return []

    prefix = f"{path}/" if path else ""

    # Discover unique next-level child names + whether they have deeper children
    child_meta: dict[str, bool] = {}  # child_name → has_deeper_children
    for folder in file_counts:
        if prefix and not folder.startswith(prefix):
            continue
        remainder = folder[len(prefix):] if prefix else folder
        if not remainder:
            continue
        parts = remainder.split("/")
        child_name = parts[0]
        if child_name not in child_meta:
            child_meta[child_name] = len(parts) > 1
        elif len(parts) > 1:
            child_meta[child_name] = True

    if not child_meta:
        return []

    # Collect all child paths for content-map lookup
    child_paths: set[str] = set()
    for name in child_meta:
        child_paths.add(f"{prefix}{name}" if prefix else name)
    content_map = _content_by_folder(child_paths)

    children: list[dict[str, Any]] = []
    for name in sorted(child_meta.keys()):
        child_path = f"{prefix}{name}" if prefix else name
        # Sum files in this folder and all its descendants
        total_files = sum(
            count
            for folder, count in file_counts.items()
            if folder == child_path or folder.startswith(f"{child_path}/")
        )
        children.append({
            "name": name,
            "path": child_path,
            "file_count": file_counts.get(child_path, 0),
            "total_file_count": total_files,
            "content": content_map.get(child_path),
            "has_children": child_meta[name],
        })

    return children
