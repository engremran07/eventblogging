from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import render

from core.constants import ADMIN_PAGINATION_SIZE
from core.models import UserProfile

User = get_user_model()

CONFIRMATION_PHRASE = "DELETE USERS"

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


class UserDeleteVerificationForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    confirmation_phrase = forms.CharField(
        help_text=f"Type {CONFIRMATION_PHRASE} exactly.",
        max_length=50,
    )
    confirm_count = forms.IntegerField(min_value=1)
    double_check = forms.BooleanField(required=True)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    fields = (
        "display_name",
        "bio",
        "avatar_url",
        "location",
        "website_url",
        "timezone",
    )


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "profile_display_name",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
        "last_login",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "groups",
        "date_joined",
        "last_login",
    )
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "profile__display_name",
        "profile__location",
    )
    ordering = ("-date_joined", "username")
    inlines = (UserProfileInline,)
    list_per_page = ADMIN_PAGINATION_SIZE
    actions = (
        "activate_selected",
        "deactivate_selected",
        "grant_staff_selected",
        "revoke_staff_selected",
        "delete_users_double_check",
    )

    @admin.action(description="Activate selected users")
    def activate_selected(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} users activated.", messages.SUCCESS)

    @admin.action(description="Deactivate selected users")
    def deactivate_selected(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} users deactivated.", messages.SUCCESS)

    @admin.action(description="Grant staff access to selected users")
    def grant_staff_selected(self, request, queryset):
        count = queryset.update(is_staff=True)
        self.message_user(request, f"{count} users granted staff access.", messages.SUCCESS)

    @admin.action(description="Revoke staff access from selected users")
    def revoke_staff_selected(self, request, queryset):
        count = queryset.update(is_staff=False)
        self.message_user(request, f"{count} users revoked from staff access.", messages.SUCCESS)

    @admin.action(description="Delete selected users (double verification required)")
    def delete_users_double_check(self, request, queryset):
        selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
        safe_queryset = queryset.exclude(pk=request.user.pk)

        if "confirm_delete" in request.POST:
            form = UserDeleteVerificationForm(request.POST)
            if form.is_valid():
                expected_count = safe_queryset.count()
                if expected_count == 0:
                    self.message_user(
                        request,
                        "No deletable users selected. You cannot delete your own active admin account with this action.",
                        messages.WARNING,
                    )
                    return HttpResponseRedirect(request.get_full_path())

                if form.cleaned_data["confirmation_phrase"] != CONFIRMATION_PHRASE:
                    self.message_user(request, "Confirmation phrase is incorrect.", messages.ERROR)
                    return HttpResponseRedirect(request.get_full_path())

                if form.cleaned_data["confirm_count"] != expected_count:
                    self.message_user(
                        request,
                        "Verification count does not match selected users.",
                        messages.ERROR,
                    )
                    return HttpResponseRedirect(request.get_full_path())

                deleted_count, _ = safe_queryset.delete()
                self.message_user(
                    request,
                    f"{deleted_count} user records deleted after double verification.",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = UserDeleteVerificationForm(
                initial={
                    helpers.ACTION_CHECKBOX_NAME: selected,
                    "confirm_count": safe_queryset.count(),
                }
            )

        context = {
            "title": "Double verification for user deletion",
            "opts": self.model._meta,
            "users": safe_queryset,
            "requested_users": queryset,
            "expected_count": safe_queryset.count(),
            "confirmation_phrase": CONFIRMATION_PHRASE,
            "verification_form": form,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        }
        return render(request, "admin/auth/user/double_delete_confirmation.html", context)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.display(ordering="profile__display_name", description="Profile")
    def profile_display_name(self, obj):
        try:
            return obj.profile.effective_name
        except UserProfile.DoesNotExist:
            return obj.get_full_name() or obj.username


@admin.register(Group)
class CustomGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "user_count", "permission_count")
    search_fields = ("name",)
    ordering = ("name",)
    filter_horizontal = ("permissions",)
    list_per_page = ADMIN_PAGINATION_SIZE

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _user_count=Count("user", distinct=True),
            _permission_count=Count("permissions", distinct=True),
        )

    @admin.display(ordering="_user_count", description="Users")
    def user_count(self, obj):
        return obj._user_count

    @admin.display(ordering="_permission_count", description="Permissions")
    def permission_count(self, obj):
        return obj._permission_count
