from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "blog"
    verbose_name = "Blog"

    def ready(self):
        from .models import Post

        model_labels = (
            (Post.categories.tag_model, "Category", "Categories"),
            (Post.primary_topic.tag_model, "Primary Topic", "Primary Topics"),
            (Post.tags.tag_model, "Tag", "Tags"),
        )
        for model, singular, plural in model_labels:
            model._meta.verbose_name = singular
            model._meta.verbose_name_plural = plural

        # Register blog-level signal handlers (publish webhook, comment moderation)
        import blog.signals  # noqa: F401
