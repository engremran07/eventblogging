"""
SEO Views — Legacy redirect views for backward compatibility.

These views redirect old URL patterns to the new control center tabs.
Split from admin_config_views.py for maintainability.
"""
from __future__ import annotations

import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponseRedirect
from django.views.decorators.http import require_GET

from .seo_views_helpers import _control_redirect, _ensure_admin_control_enabled

logger = logging.getLogger(__name__)


@staff_member_required
def legacy_action_center_redirect(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:
    """Legacy action center — redirects to discrepancies tab."""
    _ensure_admin_control_enabled()
    return _control_redirect("onsite")


@staff_member_required
@require_GET
def seo_overview(request: HttpRequest) -> HttpResponseRedirect:
    """Legacy overview page — redirects to the control center."""
    _ensure_admin_control_enabled()
    return _control_redirect("discrepancies")


@staff_member_required
def seo_engine(request: HttpRequest) -> HttpResponseRedirect:
    """Legacy engine page — redirects to settings tab."""
    _ensure_admin_control_enabled()
    return _control_redirect("settings")


@staff_member_required
@require_GET
def seo_scan(request: HttpRequest) -> HttpResponseRedirect:
    """Legacy scan page — redirects to discrepancies tab with job_id."""
    _ensure_admin_control_enabled()
    return _control_redirect("scan", job_id=request.GET.get("job_id", ""))


@staff_member_required
@require_GET
def seo_interlinks(request: HttpRequest) -> HttpResponseRedirect:
    """Legacy interlinks page — redirects to interlinking tab."""
    _ensure_admin_control_enabled()
    return _control_redirect("interlinking")


@staff_member_required
@require_GET
def seo_queue(request: HttpRequest) -> HttpResponseRedirect:
    """Legacy queue page — redirects to discrepancies tab."""
    _ensure_admin_control_enabled()
    return _control_redirect("discrepancies")
