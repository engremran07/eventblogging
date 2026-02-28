"""URL routes for tag and category autocomplete endpoints."""

from django.urls import path

from .views import CategoryAutocompleteView, TagAutocompleteView

app_name = "tags"

urlpatterns = [
    path("tag-autocomplete/", TagAutocompleteView.as_view(), name="tag_autocomplete"),
    path(
        "category-autocomplete/",
        CategoryAutocompleteView.as_view(),
        name="category_autocomplete",
    ),
]
