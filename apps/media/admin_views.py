from __future__ import annotations

import logging
import uuid
from typing import cast

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import AbstractBaseUser
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import selectors, services
from .forms import MediaEditForm, MediaUploadForm

logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 24


# ── List / Grid ─────────────────────────────────────────────────────────────


@staff_member_required  # type: ignore[type-var]
@require_GET
def admin_media_list(request: HttpRequest) -> HttpResponse:
    """Media library with folder tree navigation, search, and KPIs."""
    search = request.GET.get("q", "").strip()
    file_type = request.GET.get("file_type", "").strip()
    path = request.GET.get("path", "").strip().strip("/")
    sort_by = request.GET.get("sort", "-created_at")

    qs = selectors.get_media_list(
        search=search,
        file_type=file_type,
        path=path,
        sort_by=sort_by,
    )

    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    stats = selectors.get_media_stats()

    # Folder navigation
    child_folders = selectors.get_children_of_path(path)
    breadcrumbs = selectors.get_breadcrumbs(path)
    folder_tree = selectors.get_folder_tree()

    context = {
        "page_obj": page_obj,
        "stats": stats,
        "child_folders": child_folders,
        "breadcrumbs": breadcrumbs,
        "folder_tree": folder_tree,
        "current_path": path,
        "search": search,
        "file_type": file_type,
        "sort_by": sort_by,
    }

    if request.headers.get("HX-Request"):
        return render(request, "admin/media/partials/_browser.html", context)
    return render(request, "admin/media/list.html", context)


# ── Upload ──────────────────────────────────────────────────────────────────


@staff_member_required  # type: ignore[type-var]
@require_http_methods(["GET", "POST"])
def admin_media_upload(request: HttpRequest) -> HttpResponse:
    """Upload one or more media files."""
    if request.method == "POST":
        form = MediaUploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist("file")
            folder = form.cleaned_data.get("folder", "")
            count = 0
            for f in files:
                try:
                    services.upload_media_file(
                        file=f,
                        uploaded_by=cast(AbstractBaseUser, request.user),
                        folder=folder,
                    )
                    count += 1
                except Exception:
                    logger.warning("Failed to upload file %s", f.name, exc_info=True)

            if request.headers.get("HX-Request"):
                response = HttpResponse(status=204)
                response["HX-Trigger"] = (
                    f'{{"showToast": {{"message": "{count} file(s) uploaded", "type": "success"}}}}'
                )
                response["HX-Refresh"] = "true"
                return response
            return redirect("admin_media:list")
    else:
        form = MediaUploadForm()

    return render(request, "admin/media/upload.html", {"form": form})


# ── Edit ────────────────────────────────────────────────────────────────────


@staff_member_required  # type: ignore[type-var]
@require_http_methods(["GET", "POST"])
def admin_media_edit(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    """Edit metadata of a single media file."""
    media_file = selectors.get_media_file(pk=pk)

    if request.method == "POST":
        form = MediaEditForm(request.POST, instance=media_file)
        if form.is_valid():
            try:
                services.update_media_file(
                    media_file=media_file,
                    data=form.cleaned_data,
                )
            except Exception:
                logger.warning("Failed to update media file %s", pk, exc_info=True)
                return render(
                    request,
                    "admin/media/edit.html",
                    {"form": form, "media_file": media_file},
                    status=422,
                )
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=204)
                response["HX-Trigger"] = (
                    '{"showToast": {"message": "Media updated", "type": "success"}}'
                )
                return response
            return redirect("admin_media:list")
    else:
        form = MediaEditForm(instance=media_file)

    return render(request, "admin/media/edit.html", {"form": form, "media_file": media_file})


# ── Delete ──────────────────────────────────────────────────────────────────


@staff_member_required  # type: ignore[type-var]
@require_POST
def admin_media_delete(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    """Soft-delete a single media file."""
    media_file = selectors.get_media_file(pk=pk)
    try:
        services.delete_media_file(media_file=media_file)
    except Exception:
        logger.warning("Failed to delete media file %s", pk, exc_info=True)

    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Trigger"] = (
            '{"showToast": {"message": "File deleted", "type": "success"}}'
        )
        response["HX-Refresh"] = "true"
        return response
    return redirect("admin_media:list")


# ── Bulk Action ─────────────────────────────────────────────────────────────


@staff_member_required  # type: ignore[type-var]
@require_POST
def admin_media_bulk_action(request: HttpRequest) -> HttpResponse:
    """Handle bulk actions (currently: bulk delete)."""
    action = request.POST.get("action", "")
    raw_ids = request.POST.getlist("selected")
    pks: list[uuid.UUID] = []
    for raw in raw_ids:
        try:
            pks.append(uuid.UUID(raw))
        except (ValueError, AttributeError):
            logger.warning("Invalid UUID in bulk action: %s", raw)

    count = 0
    if action == "delete" and pks:
        try:
            count = services.bulk_delete_media(pks=pks)
        except Exception:
            logger.warning("Bulk delete failed", exc_info=True)

    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Trigger"] = (
            f'{{"showToast": {{"message": "{count} file(s) deleted", "type": "success"}}}}'
        )
        response["HX-Refresh"] = "true"
        return response
    return redirect("admin_media:list")


# ── Detail Partial (HTMX) ──────────────────────────────────────────────────


@staff_member_required  # type: ignore[type-var]
@require_GET
def admin_media_detail_partial(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    """HTMX partial: quick-view detail panel for a media file."""
    if not request.headers.get("HX-Request"):
        return redirect("admin_media:list")

    media_file = selectors.get_media_file(pk=pk)
    return render(request, "admin/media/detail_partial.html", {"media_file": media_file})
