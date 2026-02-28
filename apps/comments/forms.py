"""Forms for comments and subscriptions."""

from django import forms

from .models import Comment, NewsletterSubscriber


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4, "placeholder": "Write your comment..."}),
        }


class NewsletterSubscribeForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ("email", "full_name")
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "your@email.com"}),
            "full_name": forms.TextInput(attrs={"placeholder": "Your name (optional)"}),
        }
