from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("login/", views.core_login, name="login"),
    path("logout/", views.core_logout, name="logout"),
    path("register/", views.core_register, name="register"),
    path("profile/", views.core_profile, name="profile"),
    path("password-change/", views.core_password_change, name="password_change"),
    path("password-change/done/", views.core_password_change_done, name="password_change_done"),
    path("password-reset/", views.core_password_reset, name="password_reset"),
    path("password-reset/done/", views.core_password_reset_done, name="password_reset_done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.core_password_reset_confirm,
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.core_password_reset_complete,
        name="password_reset_complete",
    ),
]
