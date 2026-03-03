from __future__ import annotations

import logging
import mimetypes
import uuid
from io import BytesIO
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import AbstractBaseUser
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify

from .models import FileType, MediaFile

if TYPE_CHECKING:
    from blog.models import Post
    from pages.models import Page

logger = logging.getLogger(__name__)

# ── Extension-to-file-type mapping ──────────────────────────────────────────

IMAGE_EXTENSIONS = frozenset({
    "jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico", "tiff", "tif",
    "avif", "heic", "heif",
})
DOCUMENT_EXTENSIONS = frozenset({
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp",
    "txt", "csv", "rtf", "md", "epub",
})
VIDEO_EXTENSIONS = frozenset({
    "mp4", "webm", "avi", "mov", "mkv", "flv", "wmv", "m4v", "ogv",
})
AUDIO_EXTENSIONS = frozenset({
    "mp3", "wav", "ogg", "flac", "aac", "wma", "m4a", "opus",
})


def detect_file_type(filename: str) -> str:
    """Return a FileType value based on the file extension."""
    ext = PurePosixPath(filename).suffix.lstrip(".").lower()
    if ext in IMAGE_EXTENSIONS:
        return FileType.IMAGE.value
    if ext in DOCUMENT_EXTENSIONS:
        return FileType.DOCUMENT.value
    if ext in VIDEO_EXTENSIONS:
        return FileType.VIDEO.value
    if ext in AUDIO_EXTENSIONS:
        return FileType.AUDIO.value
    return FileType.OTHER.value


def detect_mime_type(filename: str) -> str:
    """Return the MIME type string for *filename* using the mimetypes module."""
    mime, _encoding = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def _get_image_dimensions(file: UploadedFile) -> tuple[int | None, int | None]:
    """Return (width, height) for an image file, or (None, None) on failure."""
    try:
        from PIL import Image

        file.seek(0)
        data = file.read()
        file.seek(0)
        img = Image.open(BytesIO(data))
        return img.size  # type: ignore[return-value]
    except Exception:
        logger.warning("Failed to read image dimensions for %s", file.name, exc_info=True)
        return None, None


def upload_media_file(
    *,
    file: UploadedFile,
    uploaded_by: AbstractBaseUser | None = None,
    folder: str = "",
    title: str = "",
    alt_text: str = "",
) -> MediaFile:
    """Create a new MediaFile from an uploaded file."""
    original_name = file.name or "untitled"
    file_type = detect_file_type(original_name)
    mime_type = detect_mime_type(original_name)
    file_size = file.size or 0

    width: int | None = None
    height: int | None = None
    if file_type == FileType.IMAGE.value:
        width, height = _get_image_dimensions(file)

    media_file = MediaFile(
        file=file,
        original_filename=original_name,
        title=title,
        alt_text=alt_text,
        file_type=file_type,
        mime_type=mime_type,
        file_size=file_size,
        width=width,
        height=height,
        uploaded_by=uploaded_by,  # type: ignore[misc]
        folder=folder,
    )
    media_file.full_clean()
    media_file.save()
    return media_file


def update_media_file(*, media_file: MediaFile, data: dict[str, Any]) -> MediaFile:
    """Update allowed fields on a MediaFile."""
    allowed_fields = {"title", "alt_text", "caption", "folder", "is_public"}
    for field, value in data.items():
        if field in allowed_fields:
            setattr(media_file, field, value)
    media_file.full_clean()
    media_file.save()
    return media_file


def delete_media_file(*, media_file: MediaFile) -> None:
    """Soft-delete a single media file."""
    media_file.is_active = False
    media_file.save(update_fields=["is_active", "updated_at"])


def bulk_delete_media(*, pks: list[uuid.UUID]) -> int:
    """Bulk soft-delete media files. Returns the number of rows updated."""
    return MediaFile.objects.filter(pk__in=pks, is_active=True).update(is_active=False)  # type: ignore[return-value]


# ── Auto-folder generation ──────────────────────────────────────────────────


def _slugify_path_segment(segment: str) -> str:
    """Slugify a single path segment, preserving hierarchy separators."""
    return slugify(segment.strip()) or "untitled"


def generate_post_media_folder(post: Post) -> str:
    """
    Build a hierarchical folder path for a blog post's media.

    Structure: ``posts/{deepest_category_path}/{post_slug}``

    Uses the **deepest** (most specific) category from the post's Tagulous
    tree tags.  For example, if a post has categories ``['technology',
    'technology/django', 'technology/frontend/design-systems']``, the deepest
    is ``technology/frontend/design-systems`` (level 3).

    Falls back to ``posts/uncategorized/{post_slug}`` when no categories.

    Examples:
        - ``posts/technology/frontend/design-systems/my-first-post``
        - ``posts/operations/devops/seed-post-01``
        - ``posts/uncategorized/untitled-post``
    """
    raw_slug = post.slug or _slugify_path_segment(post.title or "untitled")
    # Truncate long slugs to keep total file path under FileField.max_length
    slug = raw_slug[:80]

    # Categories are Tagulous tree tags — paths like "technology/frontend/htmx"
    category_path = "uncategorized"
    try:
        categories = list(post.categories.all())
        if categories:
            # Pick the deepest (most specific) category by counting "/" depth
            deepest = max(categories, key=lambda c: (getattr(c, "path", "") or getattr(c, "name", "")).count("/"))
            raw_path = getattr(deepest, "path", "") or getattr(deepest, "name", "")
            if raw_path:
                segments = [_slugify_path_segment(s) for s in raw_path.split("/") if s.strip()]
                if segments:
                    category_path = "/".join(segments)
    except Exception:
        logger.warning("generate_post_media_folder: failed to read categories for post pk=%s", post.pk, exc_info=True)

    return f"posts/{category_path}/{slug}"


def ensure_all_post_folders(*, dry_run: bool = False) -> list[str]:
    """
    Pre-build media folders for ALL posts in the database.

    Creates the physical directory on disk and returns the list of folder
    paths that were created (or would be created in dry-run mode).
    """
    import os

    from django.conf import settings as django_settings

    from blog.models import Post as PostModel

    media_root = str(django_settings.MEDIA_ROOT)
    posts = PostModel.objects.all().prefetch_related("categories")
    created: list[str] = []

    for post in posts:
        folder = generate_post_media_folder(post)
        full_path = os.path.join(media_root, folder)
        if not os.path.exists(full_path):
            if not dry_run:
                os.makedirs(full_path, exist_ok=True)
            created.append(folder)

    return created


def sync_post_media_folder(post: Post) -> int:
    """
    Update the ``folder`` field on all MediaFile records linked to *post*
    via ``post.cover_media``.  Returns the number of records updated.

    Call this after a post's slug or categories change.
    """
    folder = generate_post_media_folder(post)
    updated = 0

    # Update cover media if linked
    cover_media = getattr(post, "cover_media", None)
    if cover_media and isinstance(cover_media, MediaFile):
        if cover_media.folder != folder:
            cover_media.folder = folder
            cover_media.save(update_fields=["folder", "updated_at"])
            updated += 1

    return updated


def upload_post_cover(
    *,
    post: Post,
    file: UploadedFile,
    uploaded_by: AbstractBaseUser | None = None,
) -> MediaFile:
    """
    Upload a cover image for a blog post, automatically placing it
    in the post's hierarchical folder and linking it as ``cover_media``.
    """
    folder = generate_post_media_folder(post)

    media_file = upload_media_file(
        file=file,
        uploaded_by=uploaded_by,
        folder=folder,
        title=f"Cover: {post.title}",
        alt_text=post.title or "",
    )

    # Link to post
    from blog.models import Post as PostModel

    PostModel.objects.filter(pk=post.pk).update(cover_media=media_file)
    return media_file


# ── Page media integration ──────────────────────────────────────────────────


def generate_page_media_folder(page: Page) -> str:
    """
    Build a folder path for a page's media.

    Structure: ``pages/{page_slug}``

    Examples:
        - ``pages/about-us``
        - ``pages/privacy-policy``
        - ``pages/untitled``
    """
    raw_slug = page.slug or _slugify_path_segment(page.title or "untitled")
    slug = raw_slug[:80]
    return f"pages/{slug}"


def ensure_all_page_folders(*, dry_run: bool = False) -> list[str]:
    """
    Pre-build media folders for ALL pages in the database.

    Creates the physical directory on disk and returns the list of folder
    paths that were created (or would be created in dry-run mode).
    """
    import os

    from django.conf import settings as django_settings

    from pages.models import Page as PageModel

    media_root = str(django_settings.MEDIA_ROOT)
    pages = PageModel.objects.all()
    created: list[str] = []

    for page in pages:
        folder = generate_page_media_folder(page)
        full_path = os.path.join(media_root, folder)
        if not os.path.exists(full_path):
            if not dry_run:
                os.makedirs(full_path, exist_ok=True)
            created.append(folder)

    return created


def sync_page_media_folder(page: Page) -> int:
    """
    Update the ``folder`` field on all MediaFile records linked to *page*
    via ``page.cover_media``.  Returns the number of records updated.

    Call this after a page's slug changes.
    """
    folder = generate_page_media_folder(page)
    updated = 0

    cover_media = getattr(page, "cover_media", None)
    if cover_media and isinstance(cover_media, MediaFile):
        if cover_media.folder != folder:
            cover_media.folder = folder
            cover_media.save(update_fields=["folder", "updated_at"])
            updated += 1

    return updated


def upload_page_cover(
    *,
    page: Page,
    file: UploadedFile,
    uploaded_by: AbstractBaseUser | None = None,
) -> MediaFile:
    """
    Upload a cover image for a page, automatically placing it
    in the page's folder and linking it as ``cover_media``.
    """
    folder = generate_page_media_folder(page)

    media_file = upload_media_file(
        file=file,
        uploaded_by=uploaded_by,
        folder=folder,
        title=f"Cover: {page.title}",
        alt_text=page.title or "",
    )

    # Link to page
    from pages.models import Page as PageModel

    PageModel.objects.filter(pk=page.pk).update(cover_media=media_file)
    return media_file
