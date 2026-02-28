from django import forms

from .models import Page


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
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


class PageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Page
        fields = [
            "title",
            "slug",
            "nav_label",
            "summary",
            "body_markdown",
            "template_key",
            "show_in_navigation",
            "nav_order",
            "is_featured",
            "meta_title",
            "meta_description",
            "canonical_url",
            "status",
            "published_at",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 2}),
            "body_markdown": forms.Textarea(
                attrs={
                    "rows": 18,
                    "placeholder": "Write page content in Markdown...",
                    "data-summernote": "markdown",
                    "data-summernote-height": "460",
                }
            ),
            "meta_description": forms.Textarea(attrs={"rows": 2}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        help_texts = {
            "slug": "Leave blank to auto-generate from title.",
            "show_in_navigation": "When enabled, this page appears in top navigation.",
            "nav_order": "Lower values appear first in navigation.",
            "meta_title": "Recommended length: up to 60-70 chars.",
            "meta_description": "Recommended length: up to 160-170 chars.",
        }

    def clean_meta_title(self):
        return (self.cleaned_data.get("meta_title") or "").strip()[:70]

    def clean_meta_description(self):
        return (self.cleaned_data.get("meta_description") or "").strip()[:170]


class PageMarkdownPreviewForm(forms.Form):
    body_markdown = forms.CharField(required=False)
