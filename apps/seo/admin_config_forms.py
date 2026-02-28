from __future__ import annotations

import json

from django import forms

from .models import SeoEngineSettings, SeoSuggestion, TaxonomySynonymGroup


class SeoEngineSettingsForm(forms.ModelForm):
    class Meta:
        model = SeoEngineSettings
        fields = [
            "enable_checks",
            "enable_live_checks",
            "warn_only",
            "admin_visibility_only",
            "auto_fix_enabled",
            "auto_fix_after_hours",
            "rotation_interval_hours",
            "min_links_per_doc",
            "whitehat_cap_max_links",
            "rotation_churn_limit_percent",
            "stale_days_threshold",
            "noindex_paginated_filters",
            "canonical_query_allowlist",
            "link_suggestion_min_score",
            "autopilot_min_confidence",
            "auto_update_published_links",
            "apply_interlinks_on_audit",
        ]


class SeoSuggestionEditForm(forms.Form):
    payload_json = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 10, "class": "form-control font-monospace"}),
        help_text="Edit JSON payload before approve/reject.",
    )
    note = forms.CharField(
        required=False,
        max_length=280,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, suggestion: SeoSuggestion, **kwargs):
        self.suggestion = suggestion
        initial = kwargs.setdefault("initial", {})
        if "payload_json" not in initial:
            initial["payload_json"] = json.dumps(
                suggestion.payload_json or {},
                indent=2,
                sort_keys=True,
            )
        super().__init__(*args, **kwargs)

    def clean_payload_json(self):
        raw = self.cleaned_data["payload_json"]
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise forms.ValidationError("Payload must be a JSON object.")
        return payload


class TaxonomySynonymGroupForm(forms.ModelForm):
    class Meta:
        model = TaxonomySynonymGroup
        fields = ["name", "scope", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "scope": forms.Select(attrs={"class": "form-select"}),
        }


class TaxonomySynonymTermAddForm(forms.Form):
    term = forms.CharField(max_length=160, widget=forms.TextInput(attrs={"class": "form-control"}))
    is_canonical = forms.BooleanField(required=False)
    weight = forms.FloatField(required=False, initial=1.0, min_value=0.0)
    is_active = forms.BooleanField(required=False, initial=True)

    def clean_weight(self):
        value = self.cleaned_data.get("weight")
        if value is None:
            return 1.0
        return float(value)


class TaxonomySynonymImportForm(forms.Form):
    payload = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 14, "class": "form-control font-monospace"}),
        help_text=(
            "JSON format: "
            '[{"name":"cloud","scope":"tags","terms":[{"term":"saas","is_canonical":true}]}]'
        ),
    )

    def clean_payload(self):
        raw = self.cleaned_data["payload"]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc
        if not isinstance(parsed, list):
            raise forms.ValidationError("Import payload must be a list.")
        return parsed
