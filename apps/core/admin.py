from django.contrib import admin
from solo.admin import SingletonModelAdmin

from core.constants import ADMIN_PAGINATION_SIZE
from .models import (
    FeatureControlSettings,
    IntegrationSettings,
    SeoSettings,
    SiteAppearanceSettings,
    SiteIdentitySettings,
    UserProfile,
)


@admin.register(SiteIdentitySettings)
class SiteIdentitySettingsAdmin(SingletonModelAdmin):
    pass


@admin.register(SeoSettings)
class SeoSettingsAdmin(SingletonModelAdmin):
    pass


@admin.register(IntegrationSettings)
class IntegrationSettingsAdmin(SingletonModelAdmin):
    pass


@admin.register(FeatureControlSettings)
class FeatureControlSettingsAdmin(SingletonModelAdmin):
    pass


@admin.register(SiteAppearanceSettings)
class SiteAppearanceSettingsAdmin(SingletonModelAdmin):
    pass


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "timezone", "updated_at")
    search_fields = ("user__username", "user__email", "display_name", "bio")
    list_filter = ("timezone",)
    list_per_page = ADMIN_PAGINATION_SIZE
