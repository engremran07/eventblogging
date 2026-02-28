"""Tags and categories management.

This app manages the tag/category taxonomy for blog posts.
Uses Tagulous for the underlying tag implementation.
All TagField instances are auto-managed by Tagulous.
"""

from django.apps import AppConfig


class TagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tags"
    verbose_name = "Tags & Categories"
