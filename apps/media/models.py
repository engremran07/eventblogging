from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel


class FileType(models.TextChoices):
    IMAGE = "image", "Image"
    DOCUMENT = "document", "Document"
    VIDEO = "video", "Video"
    AUDIO = "audio", "Audio"
    OTHER = "other", "Other"


def media_upload_path(instance: MediaFile, filename: str) -> str:
    """
    Generate upload path based on the ``folder`` field.

    Path structure:
        - If folder is set:  ``{folder}/{unique_name}``
        - Otherwise:         ``uploads/{YYYY}/{MM}/{unique_name}``

    A short UUID prefix ensures uniqueness while preserving the original extension.
    """
    ext = PurePosixPath(filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex[:12]}{ext}"

    folder = (instance.folder or "").strip().strip("/")
    if folder:
        return f"{folder}/{unique_name}"

    now = timezone.now()
    return f"uploads/{now.year}/{now.month:02d}/{unique_name}"


class MediaFile(BaseModel):
    """A managed media file (image, document, video, audio, or other)."""

    file = models.FileField(upload_to=media_upload_path, max_length=512)
    original_filename = models.CharField(max_length=260)
    title = models.CharField(max_length=260, blank=True)
    alt_text = models.CharField(max_length=260, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER.value,
    )
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_media",
    )
    folder = models.CharField(max_length=260, blank=True, db_index=True)
    is_public = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["file_type", "is_active"]),
            models.Index(fields=["folder", "is_active"]),
        ]
        verbose_name = "Media File"
        verbose_name_plural = "Media Files"

    def __str__(self) -> str:
        return self.title or self.original_filename

    def get_absolute_url(self) -> str:
        return self.file_url

    @property
    def is_image(self) -> bool:
        return self.file_type == FileType.IMAGE.value

    @property
    def extension(self) -> str:
        if self.original_filename and "." in self.original_filename:
            return self.original_filename.rsplit(".", maxsplit=1)[-1].lower()
        return ""

    @property
    def file_url(self) -> str:
        if self.file:
            return self.file.url  # type: ignore[return-value]
        return ""
