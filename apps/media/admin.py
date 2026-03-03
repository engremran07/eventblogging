from __future__ import annotations

from django.contrib import admin

from .models import MediaFile


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "__str__",
        "file_type",
        "mime_type",
        "file_size",
        "folder",
        "uploaded_by",
        "is_active",
        "created_at",
    ]
    list_filter = ["file_type", "is_active", "is_public", "folder"]
    search_fields = ["title", "original_filename"]
    readonly_fields = [
        "original_filename",
        "file_type",
        "mime_type",
        "file_size",
        "width",
        "height",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["uploaded_by"]
    date_hierarchy = "created_at"
