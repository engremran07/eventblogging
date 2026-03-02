from django.urls import path

from . import admin_config_views as views

app_name = "admin_config"

urlpatterns = [
    # ── Control Center (4-tab dashboard) ─────────────────────────────────
    path("control/", views.seo_control_center, name="seo_control"),
    path("control/run/", views.seo_control_run, name="seo_control_run"),
    path("control/autopilot/", views.seo_control_autopilot, name="seo_control_autopilot"),
    path(
        "control/section/<slug:section>/",
        views.seo_control_section,
        name="seo_control_section",
    ),
    path(
        "control/settings/save/",
        views.seo_control_settings_save,
        name="seo_control_settings_save",
    ),
    path(
        "control/jobs/<int:job_id>/progress/",
        views.seo_control_job_progress,
        name="seo_control_job_progress",
    ),
    path(
        "control/suggestions/<int:suggestion_id>/edit/",
        views.seo_control_suggestion_edit,
        name="seo_control_suggestion_edit",
    ),
    path(
        "control/suggestions/<int:suggestion_id>/<str:action>/",
        views.seo_control_suggestion_action,
        name="seo_control_suggestion_action",
    ),
    path(
        "control/suggestions/bulk/",
        views.seo_control_suggestion_bulk,
        name="seo_control_suggestion_bulk",
    ),
    path(
        "control/<slug:section>/",
        views.seo_control_center,
        name="seo_control_canonical_section",
    ),
    # ── Scan / Interlink POST endpoints ──────────────────────────────────
    path("scan/start/", views.seo_scan_start, name="seo_scan_start"),
    path(
        "interlinks/scan/start/",
        views.seo_interlink_scan_start,
        name="seo_interlink_scan_start",
    ),
    path(
        "scan/jobs/<int:job_id>/cancel/",
        views.seo_scan_job_cancel,
        name="seo_scan_job_cancel",
    ),
    # ── Taxonomy (synonyms) ──────────────────────────────────────────────
    path("taxonomy/synonyms/", views.taxonomy_synonyms, name="taxonomy_synonyms"),
    path(
        "taxonomy/synonyms/groups/create/",
        views.taxonomy_synonym_group_create,
        name="taxonomy_synonym_group_create",
    ),
    path(
        "taxonomy/synonyms/groups/<int:group_id>/terms/add/",
        views.taxonomy_synonym_term_add,
        name="taxonomy_synonym_term_add",
    ),
    path(
        "taxonomy/synonyms/groups/<int:group_id>/terms/remove/",
        views.taxonomy_synonym_term_remove,
        name="taxonomy_synonym_term_remove",
    ),
    path(
        "taxonomy/synonyms/import/",
        views.taxonomy_synonym_import,
        name="taxonomy_synonym_import",
    ),
    path(
        "taxonomy/synonyms/export/",
        views.taxonomy_synonym_export,
        name="taxonomy_synonym_export",
    ),
    # ── Legacy redirects (kept for backward compat + tests) ──────────────
    path("overview/", views.seo_overview, name="seo_overview"),
    path("engine/", views.seo_engine, name="seo_engine"),
    path("scan/", views.seo_scan, name="seo_scan"),
    path("interlinks/", views.seo_interlinks, name="seo_interlinks"),
    path("queue/", views.seo_queue, name="seo_queue"),
    path(
        "action-center/",
        views.legacy_action_center_redirect,
        name="seo_action_center",
    ),
    path(
        "action-center/panel/",
        views.legacy_action_center_redirect,
        name="seo_action_center_panel",
    ),
    path(
        "action-center/bulk/",
        views.legacy_action_center_redirect,
        name="seo_action_center_bulk",
    ),
    path(
        "action-center/suggestion/<int:suggestion_id>/<str:action>/",
        views.legacy_action_center_redirect,
        name="seo_action_center_single",
    ),
]
