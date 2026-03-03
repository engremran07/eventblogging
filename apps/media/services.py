from __future__ import annotations

import logging
import mimetypes
import uuid
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.core.files.uploadedfile import UploadedFile

from .models import FileType, MediaFile

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
