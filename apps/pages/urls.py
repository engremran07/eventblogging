from django.urls import path

from . import views

app_name = "pages"

urlpatterns = [
    path("", views.page_list, name="list"),
    path("policies/", views.policy_index, name="policy_index"),
    path("policies/<slug:slug>/", views.policy_detail, name="policy_detail"),
    path("manage/", views.page_manage, name="manage"),
    path("manage/bulk-action/", views.page_bulk_action, name="bulk_action"),
    path("new/", views.page_create, name="create"),
    path("editor/preview/", views.markdown_preview, name="markdown_preview"),
    path("api/pages/", views.api_pages, name="api_pages"),
    path("<slug:slug>/", views.page_detail, name="detail"),
    path("<slug:slug>/edit/", views.page_update, name="update"),
    path("<slug:slug>/delete/", views.page_delete, name="delete"),
    path("<slug:slug>/revisions/", views.page_revisions, name="revisions"),
]
