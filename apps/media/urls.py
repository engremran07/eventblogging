from __future__ import annotations

from django.urls import path

from . import admin_views

app_name = "admin_media"

urlpatterns = [
    path("", admin_views.admin_media_list, name="list"),
    path("upload/", admin_views.admin_media_upload, name="upload"),
    path("<uuid:pk>/edit/", admin_views.admin_media_edit, name="edit"),
    path("<uuid:pk>/delete/", admin_views.admin_media_delete, name="delete"),
    path("bulk-action/", admin_views.admin_media_bulk_action, name="bulk_action"),
    path("hx/<uuid:pk>/detail/", admin_views.admin_media_detail_partial, name="detail_partial"),
]
