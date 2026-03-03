from __future__ import annotations

from django import forms

from .models import MediaFile


class MultipleFileInput(forms.FileInput):
    """FileInput widget that allows selecting multiple files."""

    allow_multiple_selected = True


class MediaUploadForm(forms.Form):
    """Form for uploading one or more media files."""

    file = forms.FileField(
        widget=MultipleFileInput(attrs={"class": "form-control"}),
    )
    folder = forms.CharField(
        max_length=260,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. blog/covers"}),
    )
    is_public = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class MediaEditForm(forms.ModelForm):
    """Form for editing metadata of an existing media file."""

    class Meta:
        model = MediaFile
        fields = ["title", "alt_text", "caption", "folder", "is_public"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "alt_text": forms.TextInput(attrs={"class": "form-control"}),
            "caption": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "folder": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. blog/covers"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
