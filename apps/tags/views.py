"""
Tags app: utilities for tag/category management and Tagulous integration.
Tagulous auto-creates Tag and Category models from TagField declarations on Post.
This app provides additional tag-related views and utilities.
"""

from django.http import JsonResponse
from django.views.generic import View

from blog.models import Post


class TagAutocompleteView(View):
    """HTMX autocomplete endpoint for tags."""

    def get(self, request):
        query = request.GET.get("q", "").strip()
        tag_model = Post.tags.tag_model
        
        if query:
            tags = tag_model.objects.filter(name__icontains=query).values_list("name", flat=True)[:20]
        else:
            tags = tag_model.objects.values_list("name", flat=True).order_by("-count")[:20]
        
        return JsonResponse({"results": [{"id": t, "text": t} for t in tags]})


class CategoryAutocompleteView(View):
    """HTMX autocomplete endpoint for categories (with tree support)."""

    def get(self, request):
        query = request.GET.get("q", "").strip()
        category_model = Post.categories.tag_model
        
        if query:
            categories = category_model.objects.filter(name__icontains=query).values_list(
                "name", flat=True
            )[:20]
        else:
            categories = category_model.objects.values_list("name", flat=True).order_by(
                "-count"
            )[:20]
        
        return JsonResponse({"results": [{"id": c, "text": c} for c in categories]})
