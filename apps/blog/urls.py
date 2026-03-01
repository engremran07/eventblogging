from django.urls import path

from . import admin_views, views

app_name = "blog"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/posts/bulk-action/", views.post_bulk_action, name="post_bulk_action"),
    path("search/suggestions/", views.search_suggestions, name="search_suggestions"),
    path("post/new/", views.post_create, name="post_create"),
    path("post/<slug:slug>/", views.post_detail, name="post_detail"),
    path("post/<slug:slug>/quick-preview/", views.post_quick_preview, name="post_quick_preview"),
    path("post/<slug:slug>/edit/", views.post_update, name="post_update"),
    path("post/<slug:slug>/delete/", views.post_delete, name="post_delete"),
    path("post/<slug:slug>/revisions/", views.post_revisions, name="post_revisions"),
    path("post/<slug:slug>/comment/", views.comment_create, name="comment_create"),
    path("post/<slug:slug>/comments/bulk-action/", views.comment_bulk_action, name="comment_bulk_action"),
    path("comment/<int:comment_id>/edit/", views.comment_update, name="comment_update"),
    path("comment/<int:comment_id>/delete/", views.comment_delete, name="comment_delete"),
    path("post/<slug:slug>/like/", views.toggle_like, name="toggle_like"),
    path("post/<slug:slug>/bookmark/", views.toggle_bookmark, name="toggle_bookmark"),
    path("topic/<str:topic_name>/", views.posts_by_topic, name="posts_by_topic"),
    path("tag/<str:tag_name>/", views.posts_by_tag, name="posts_by_tag"),
    path(
        "category/<path:category_name>/",
        views.posts_by_category,
        name="posts_by_category",
    ),
    path("autocomplete/topic/", views.topic_autocomplete, name="topic_autocomplete"),
    path("autocomplete/tag/", views.tag_autocomplete, name="tag_autocomplete"),
    path(
        "autocomplete/category/",
        views.category_autocomplete,
        name="category_autocomplete",
    ),
    path("editor/preview/", views.markdown_preview, name="markdown_preview"),
    path("newsletter/subscribe/", views.newsletter_subscribe, name="newsletter_subscribe"),
    path("api/posts/", views.api_posts, name="api_posts"),
    path("api/appearance-state/", views.api_appearance_state, name="api_appearance_state"),
    path("api/dashboard/stats/", views.api_dashboard_stats, name="api_dashboard_stats"),
    path("api/dashboard/stats/stream/", views.dashboard_stats_stream, name="dashboard_stats_stream"),

    # ────────────────────────────────────────────────────────────────────────────────
    # Admin Content Management (Phase 5)
    # ────────────────────────────────────────────────────────────────────────────────
    path("admin/", admin_views.admin_dashboard, name="admin_dashboard"),
    path("admin/posts/", admin_views.admin_posts_list, name="admin_posts_list"),
    path("admin/posts/bulk-action/", admin_views.admin_posts_bulk_action, name="admin_posts_bulk_action"),
    path("admin/posts/bulk-delete/", admin_views.admin_bulk_delete_posts, name="admin_bulk_delete_posts"),
    path("admin/posts/<int:post_id>/edit/", admin_views.admin_post_editor, name="admin_post_editor"),
    path("admin/posts/new/", admin_views.admin_post_editor, name="admin_post_create"),
    path("admin/comments/", admin_views.admin_comments_list, name="admin_comments_list"),
    path("admin/comments/bulk-action/", admin_views.admin_comments_bulk_action, name="admin_comments_bulk_action"),
    path("admin/comments/<int:comment_id>/approve/", admin_views.admin_comment_approve, name="admin_comment_approve"),
    path("admin/comments/<int:comment_id>/delete/", admin_views.admin_comment_delete, name="admin_comment_delete"),
    path("admin/settings/", admin_views.admin_settings, name="admin_settings"),
    path(
        "admin/settings/theme-toggle/",
        admin_views.admin_settings_theme_toggle,
        name="admin_settings_theme_toggle",
    ),
]
