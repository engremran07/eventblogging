from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from core.models import FeatureControlSettings, UserProfile
from core.session import SessionService


class AdminAppearanceRoutingTests(TestCase):
    def test_admin_appearance_change_url_reverses(self):
        url = reverse("admin:core_siteappearancesettings_change", args=[1])
        self.assertEqual(url, "/admin/core/siteappearancesettings/1/change/")

    def test_admin_index_renders_for_superuser(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass1234",
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/admin/core.js")

    def test_admin_shell_uses_post_logout_forms(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            username="admin_logout_forms",
            email="admin_logout_forms@example.com",
            password="pass1234",
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'method="post" action="/admin/logout/"')

    def test_custom_admin_posts_route_renders(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            username="admin_posts",
            email="admin_posts@example.com",
            password="pass1234",
        )
        self.client.force_login(admin_user)
        response = self.client.get("/admin/posts/")
        self.assertEqual(response.status_code, 200)

    def test_custom_admin_bulk_delete_route_reverses(self):
        url = reverse("admin_bulk_delete_posts")
        self.assertEqual(url, "/admin/posts/bulk-delete/")

    def test_custom_admin_posts_bulk_action_route_reverses(self):
        url = reverse("admin_posts_bulk_action")
        self.assertEqual(url, "/admin/posts/bulk-action/")

    def test_custom_admin_comments_route_renders(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(
            username="admin_comments",
            email="admin_comments@example.com",
            password="pass1234",
        )
        self.client.force_login(admin_user)
        response = self.client.get("/admin/comments/")
        self.assertEqual(response.status_code, 200)


class SessionServiceTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.session_middleware = SessionMiddleware(lambda request: None)

    def _request_with_session(self):
        request = self.factory.get("/")
        self.session_middleware.process_request(request)
        return request

    def test_ensure_session_key_creates_key(self):
        request = self._request_with_session()
        self.assertIsNone(request.session.session_key)

        session_key = SessionService.ensure_session_key(request)

        self.assertTrue(session_key)
        self.assertEqual(request.session.session_key, session_key)

    def test_fingerprint_is_stable_and_not_raw_session_key(self):
        request = self._request_with_session()

        fingerprint_one = SessionService.fingerprint(request)
        fingerprint_two = SessionService.fingerprint(request)

        self.assertTrue(fingerprint_one)
        self.assertEqual(fingerprint_one, fingerprint_two)
        self.assertNotEqual(fingerprint_one, request.session.session_key)

    def test_marker_key_is_namespaced_and_mark_round_trips(self):
        request = self._request_with_session()
        self.assertFalse(SessionService.is_marked(request, "post_view", 42))

        SessionService.mark(request, "post_view", 42)

        self.assertTrue(SessionService.is_marked(request, "post_view", 42))
        self.assertEqual(
            SessionService.marker_key("post_view", 42),
            "djangoblog:post_view:42",
        )


class CoreAuthRoutingTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="127.0.0.1")

    def test_login_logout_urls_are_centralized_under_auth_prefix(self):
        self.assertEqual(reverse("login"), "/auth/login/")
        self.assertEqual(reverse("logout"), "/auth/logout/")
        self.assertEqual(reverse("profile"), "/auth/profile/")
        self.assertEqual(reverse("register"), "/auth/register/")
        self.assertEqual(reverse("password_reset"), "/auth/password-reset/")
        self.assertEqual(reverse("password_change"), "/auth/password-change/")

    def test_non_staff_user_can_login_via_core_login(self):
        user = get_user_model().objects.create_user(
            username="core_auth_writer",
            password="strong-password",
        )
        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "strong-password"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), reverse("blog:dashboard"))

    def test_admin_login_still_rejects_non_staff(self):
        user = get_user_model().objects.create_user(
            username="core_auth_nonstaff",
            password="strong-password",
        )
        response = self.client.post(
            reverse("admin:login"),
            {"username": user.username, "password": "strong-password"},
            follow=False,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "staff account")


class UserProfileTests(TestCase):
    def test_profile_is_auto_created_for_new_user(self):
        user = get_user_model().objects.create_user(
            username="profile_auto_user",
            password="strong-password",
            email="profile_auto_user@example.com",
        )
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_profile_page_renders_for_authenticated_user(self):
        user = get_user_model().objects.create_user(
            username="profile_page_user",
            password="strong-password",
            email="profile_page_user@example.com",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile Settings")

    def test_register_is_404_when_registration_disabled(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_user_registration = False
        controls.save(update_fields=["enable_user_registration", "updated_at"])

        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 404)

    def test_register_creates_account_when_enabled(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_user_registration = True
        controls.save(update_fields=["enable_user_registration", "updated_at"])

        response = self.client.post(
            reverse("register"),
            {
                "username": "new_registered_user",
                "email": "new_registered_user@example.com",
                "first_name": "New",
                "last_name": "User",
                "password1": "StrongPassword-123",
                "password2": "StrongPassword-123",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            get_user_model().objects.filter(username="new_registered_user").exists()
        )


class PlatformGuardMiddlewareTests(TestCase):
    def test_maintenance_mode_blocks_non_staff(self):
        controls = FeatureControlSettings.get_solo()
        controls.maintenance_mode = True
        controls.save(update_fields=["maintenance_mode", "updated_at"])

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Scheduled Maintenance", status_code=503)

    def test_maintenance_mode_allows_staff(self):
        controls = FeatureControlSettings.get_solo()
        controls.maintenance_mode = True
        controls.save(update_fields=["maintenance_mode", "updated_at"])
        staff = get_user_model().objects.create_superuser(
            username="maintenance_staff",
            email="maintenance_staff@example.com",
            password="strong-password",
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 200)

    def test_read_only_mode_blocks_non_staff_posts(self):
        controls = FeatureControlSettings.get_solo()
        controls.read_only_mode = True
        controls.save(update_fields=["read_only_mode", "updated_at"])

        response = self.client.post(
            reverse("blog:newsletter_subscribe"),
            {"email": "readonly@example.com"},
        )
        self.assertEqual(response.status_code, 503)
