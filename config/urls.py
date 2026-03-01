from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from blog import admin_views as blog_admin_views

from . import views as config_views

# Custom error handlers
handler404 = "config.views.handler404_view"
handler500 = "config.views.handler500_view"

urlpatterns = [
    path(
        "admin/seo/",
        include(("seo.admin_urls", "admin_config"), namespace="admin_config"),
    ),
    # Custom content workspace under /admin/* must be declared before admin.site.urls
    # to avoid being consumed by Django admin's catch-all resolver.
    path("admin/posts/", blog_admin_views.admin_posts_list, name="admin_posts_list"),
    path("admin/posts/new/", blog_admin_views.admin_post_editor, name="admin_post_create"),
    path(
        "admin/posts/<int:post_id>/edit/",
        blog_admin_views.admin_post_editor,
        name="admin_post_editor",
    ),
    path(
        "admin/posts/bulk-action/",
        blog_admin_views.admin_posts_bulk_action,
        name="admin_posts_bulk_action",
    ),
    path(
        "admin/posts/bulk-delete/",
        blog_admin_views.admin_bulk_delete_posts,
        name="admin_bulk_delete_posts",
    ),
    path("admin/comments/", blog_admin_views.admin_comments_list, name="admin_comments_list"),
    path(
        "admin/comments/<int:comment_id>/approve/",
        blog_admin_views.admin_comment_approve,
        name="admin_comment_approve",
    ),
    path(
        "admin/comments/<int:comment_id>/delete/",
        blog_admin_views.admin_comment_delete,
        name="admin_comment_delete",
    ),
    path(
        "admin/comments/bulk-action/",
        blog_admin_views.admin_comments_bulk_action,
        name="admin_comments_bulk_action",
    ),
    path("admin/pages/", blog_admin_views.admin_pages_list, name="admin_pages_list"),
    path(
        "admin/pages/bulk-action/",
        blog_admin_views.admin_pages_bulk_action,
        name="admin_pages_bulk_action",
    ),
    path("admin/tags/", blog_admin_views.admin_tags_list, name="admin_tags_list"),
    path(
        "admin/tags/bulk-action/",
        blog_admin_views.admin_tags_bulk_action,
        name="admin_tags_bulk_action",
    ),
    path(
        "admin/categories/",
        blog_admin_views.admin_categories_list,
        name="admin_categories_list",
    ),
    path(
        "admin/categories/bulk-action/",
        blog_admin_views.admin_categories_bulk_action,
        name="admin_categories_bulk_action",
    ),
    path(
        "admin/categories/reparent/",
        blog_admin_views.admin_categories_reparent,
        name="admin_categories_reparent",
    ),
    path("admin/topics/", blog_admin_views.admin_topics_list, name="admin_topics_list"),
    path(
        "admin/topics/bulk-action/",
        blog_admin_views.admin_topics_bulk_action,
        name="admin_topics_bulk_action",
    ),
    path("admin/users/", blog_admin_views.admin_users_list, name="admin_users_list"),
    path(
        "admin/users/bulk-action/",
        blog_admin_views.admin_users_bulk_action,
        name="admin_users_bulk_action",
    ),
    path("admin/groups/", blog_admin_views.admin_groups_list, name="admin_groups_list"),
    path(
        "admin/groups/bulk-action/",
        blog_admin_views.admin_groups_bulk_action,
        name="admin_groups_bulk_action",
    ),
    path("admin/settings/", blog_admin_views.admin_settings, name="admin_settings"),
    path(
        "admin/settings/theme-toggle/",
        blog_admin_views.admin_settings_theme_toggle,
        name="admin_settings_theme_toggle",
    ),
    path("auth/", include("core.urls")),
    path("admin/", admin.site.urls),
    path("api/", include("seo.urls")),
    path("api/", include("tags.urls")),
    path("sitemap.xml", config_views.sitemap_sections_index, name="sitemap-index"),
    path("sitemap-index.xml", config_views.sitemap_sections_index, name="sitemap-sections-index"),
    path("sitemap-unified.xml", config_views.sitemap_unified, name="sitemap-unified"),
    path("sitemap-<section>.xml", config_views.sitemap_section, name="sitemap-section"),
    path("sitemap.xsl", config_views.sitemap_xsl, name="sitemap-xsl"),
    path("robots.txt", config_views.robots_txt, name="robots-txt"),
    path("pages/", include("pages.urls")),
    path("", include("blog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar  # noqa: F401  # type: ignore[import-untyped]
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    except ImportError:
        pass
