from django.urls import path

from . import views

app_name = "seo"

urlpatterns = [
    path(
        "seo/live-check/<str:content_type>/",
        views.live_check_inline,
        name="live_check_inline",
    ),
    path("search/semantic", views.search_semantic, name="search_semantic"),
    path("related/<int:post_id>/semantic", views.related_semantic, name="related_semantic"),
    path("semantic/reindex/<int:post_id>", views.reindex_post, name="reindex_post"),
    path(
        "semantic/review/<int:candidate_id>/approve",
        views.review_approve,
        name="review_approve",
    ),
    path(
        "semantic/review/<int:candidate_id>/reject",
        views.review_reject,
        name="review_reject",
    ),
    path("semantic/dashboard/stats", views.dashboard_stats, name="dashboard_stats"),
]
