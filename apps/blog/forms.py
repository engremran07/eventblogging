from django import forms
from django.utils import timezone

from comments.models import Comment, NewsletterSubscriber

from .models import Post
from .taxonomy_rules import category_depth_help_text, validate_category_depth


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
                continue

            if isinstance(widget, forms.FileInput):
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} form-control".strip()
                continue

            if isinstance(
                widget,
                (
                    forms.TextInput,
                    forms.Textarea,
                    forms.Select,
                    forms.SelectMultiple,
                    forms.DateTimeInput,
                    forms.EmailInput,
                    forms.URLInput,
                ),
            ):
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} form-control".strip()

            if name in {"tags", "categories", "primary_topic"}:
                widget.attrs["placeholder"] = "Type to add or search tags"


class PostForm(BootstrapFormMixin, forms.ModelForm):
    published_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
            }
        ),
        help_text="Optional schedule. Published posts go live at this time.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "categories" in self.fields:
            self.fields["categories"].help_text = category_depth_help_text()
        if "published_at" in self.fields:
            value = getattr(self.instance, "published_at", None)
            if value:
                local_value = timezone.localtime(value)
                self.initial["published_at"] = local_value.strftime("%Y-%m-%dT%H:%M")

    class Meta:
        model = Post
        fields = [
            "title",
            "slug",
            "excerpt",
            "cover_image",
            "body_markdown",
            "meta_title",
            "meta_description",
            "canonical_url",
            "primary_topic",
            "tags",
            "categories",
            "published_at",
            "status",
            "is_featured",
            "is_editors_pick",
            "allow_comments",
            "allow_reactions",
        ]
        widgets = {
            "slug": forms.TextInput(
                attrs={"placeholder": "auto-generated-from-title"}
            ),
            "excerpt": forms.Textarea(attrs={"rows": 2}),
            "body_markdown": forms.Textarea(
                attrs={
                    "rows": 18,
                    "placeholder": "Write Markdown content...",
                    "data-summernote": "markdown",
                    "data-summernote-height": "460",
                }
            ),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {
            "slug": "Leave blank to auto-generate from title. Edit only if you need a custom URL.",
            "meta_title": "Recommended length: up to 60-70 chars.",
            "meta_description": "Recommended length: up to 160-170 chars.",
            "canonical_url": "Optional canonical URL for syndicated content.",
            "is_editors_pick": "Highlights this post in editorial sections.",
            "categories": "Nested categories are supported.",
        }

    def clean_meta_title(self):
        value = self.cleaned_data.get("meta_title", "").strip()
        return value[:70]

    def clean_meta_description(self):
        value = self.cleaned_data.get("meta_description", "").strip()
        return value[:170]

    def clean_categories(self):
        categories = self.cleaned_data.get("categories", []) or []
        category_names = [getattr(tag, "name", str(tag)) for tag in categories]
        validate_category_depth(category_names)
        return categories

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        if status and status != Post.Status.PUBLISHED:
            cleaned["published_at"] = None
        return cleaned


class CommentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Add a thoughtful comment...",
                }
            )
        }


class NewsletterForm(BootstrapFormMixin, forms.ModelForm):
    company = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = NewsletterSubscriber
        fields = ["full_name", "email"]
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Your name (optional)"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
        }

    def clean_company(self):
        value = self.cleaned_data.get("company")
        if value:
            raise forms.ValidationError("Invalid submission.")
        return value

    def validate_unique(self):
        # Existing subscriber handling (already subscribed/reactivate) is managed in the view.
        return


class MarkdownPreviewForm(forms.Form):
    body_markdown = forms.CharField(required=False)


class PostFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search posts, tags, topics, categories...",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
    )
    topic = forms.CharField(required=False)
    tag = forms.CharField(required=False)
    category = forms.CharField(required=False)
    featured = forms.BooleanField(required=False)
    mode = forms.ChoiceField(
        required=False,
        choices=[
            ("all", "All Posts"),
            ("editors", "Editors Picks"),
            ("featured", "Featured"),
        ],
        initial="all",
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("latest", "Latest"),
            ("trending", "Trending"),
            ("popular", "Popular"),
        ],
        initial="latest",
    )
