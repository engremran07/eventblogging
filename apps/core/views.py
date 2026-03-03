"""
Core authentication views.

Auth is centralized here as the single source of truth for non-admin sessions.
"""

from __future__ import annotations

from typing import Any, cast

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from .forms import CoreRegistrationForm, UserAccountForm, UserProfileForm
from .models import FeatureControlSettings, UserProfile


class CoreLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class CoreLogoutView(LogoutView):
    next_page = reverse_lazy("blog:home")


class CorePasswordChangeView(PasswordChangeView):
    success_url = reverse_lazy("core:password_change_done")


class CorePasswordResetView(PasswordResetView):
    success_url = reverse_lazy("core:password_reset_done")


class CorePasswordResetConfirmView(PasswordResetConfirmView):
    success_url = reverse_lazy("core:password_reset_complete")


@require_http_methods(["GET", "POST"])
def core_register(request: HttpRequest) -> HttpResponse:
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_user_registration:
        raise Http404("User registration is disabled.")

    if request.user.is_authenticated:
        return redirect("blog:dashboard")

    form = CoreRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.get_for_user(user)
        login(request, user)
        messages.success(request, "Account created successfully.")
        return redirect("blog:dashboard")

    return render(request, "registration/register.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def core_profile(request: HttpRequest) -> HttpResponse:
    user = cast(User, request.user)
    profile = UserProfile.get_for_user(user)
    account_form = UserAccountForm(request.POST or None, instance=user)
    profile_form = UserProfileForm(request.POST or None, instance=profile)

    if request.method == "POST":
        if account_form.is_valid() and profile_form.is_valid():
            account_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("core:profile")
        messages.error(request, "Unable to update profile.")

    metrics: dict[str, Any] = {
        "post_count": user.posts.count() if hasattr(user, "posts") else 0,  # type: ignore[attr-defined]
        "comment_count": user.post_comments.count()  # type: ignore[attr-defined]
        if hasattr(user, "post_comments")
        else 0,
        "like_count": user.liked_posts.count() if hasattr(user, "liked_posts") else 0,  # type: ignore[attr-defined]
        "bookmark_count": user.bookmarked_posts.count()  # type: ignore[attr-defined]
        if hasattr(user, "bookmarked_posts")
        else 0,
    }

    return render(
        request,
        "registration/profile.html",
        {
            "account_form": account_form,
            "profile_form": profile_form,
            "profile_metrics": metrics,
        },
    )


core_login = CoreLoginView.as_view()
core_logout = CoreLogoutView.as_view()
core_password_change = CorePasswordChangeView.as_view()
core_password_change_done = PasswordChangeDoneView.as_view()
core_password_reset = CorePasswordResetView.as_view()
core_password_reset_done = PasswordResetDoneView.as_view()
core_password_reset_confirm = CorePasswordResetConfirmView.as_view()
core_password_reset_complete = PasswordResetCompleteView.as_view()
