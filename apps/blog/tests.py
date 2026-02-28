from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comments.models import Comment, NewsletterSubscriber, PostLike, PostView
from .models import Post
from .ui_feedback import attach_ui_feedback
from pages.models import Page
from core.constants import ADMIN_PAGINATION_SIZE
from core.models import (
    FeatureControlSettings,
    IntegrationSettings,
    SeoSettings,
    SiteAppearanceSettings,
    SiteIdentitySettings,
)


class BlogTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="writer",
            password="strong-password",
        )
        self.commenter = get_user_model().objects.create_user(
            username="commenter",
            password="strong-password",
        )

    def _create_post(self, title="Post", status=Post.Status.PUBLISHED):
        return Post.objects.create(
            author=self.user,
            title=title,
            body_markdown="Hello world from markdown content",
            status=status,
            excerpt="Short excerpt",
        )

    def _get_ui_feedback(self, response):
        trigger = response.headers.get("HX-Trigger", "{}")
        payload = json.loads(trigger)
        return payload.get("ui:feedback", {})

    def test_post_slug_and_meta_are_generated(self):
        post = self._create_post(title="Ultimate Django Stack")
        self.assertTrue(post.slug.startswith("ultimate-django-stack"))
        self.assertTrue(post.meta_title)
        self.assertTrue(post.meta_description)
        self.assertGreater(post.word_count, 0)

    def test_home_hides_drafts_from_anonymous_users(self):
        self._create_post(title="Public Post", status=Post.Status.PUBLISHED)
        self._create_post(title="Draft Post", status=Post.Status.DRAFT)

        response = self.client.get(reverse("blog:home"))
        self.assertContains(response, "Public Post")
        self.assertNotContains(response, "Draft Post")

    def test_newsletter_subscribe_creates_subscriber(self):
        response = self.client.post(
            reverse("blog:newsletter_subscribe"),
            {"email": "new@example.com", "full_name": "New User", "company": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            NewsletterSubscriber.objects.filter(email="new@example.com").exists()
        )

    def test_newsletter_subscribe_respects_global_feature_toggle(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_newsletter = False
        controls.save(update_fields=["enable_newsletter", "updated_at"])

        response = self.client.post(
            reverse("blog:newsletter_subscribe"),
            {"email": "disabled@example.com", "full_name": "Disabled User", "company": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            NewsletterSubscriber.objects.filter(email="disabled@example.com").exists()
        )

    def test_markdown_preview_requires_login(self):
        response = self.client.post(
            reverse("blog:markdown_preview"),
            {"body_markdown": "# Heading"},
        )
        self.assertEqual(response.status_code, 302)

    def test_markdown_preview_sanitizes_script(self):
        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:markdown_preview"),
            {"body_markdown": "<script>alert('x')</script>\n\n# Safe"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>")

    def test_markdown_preview_preserves_summernote_rich_styles_and_tables(self):
        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:markdown_preview"),
            {
                "body_markdown": (
                    '<p><span style="color:#ff0000;font-size:18px;font-family:Arial">Styled text</span></p>'
                    '<table style="width:100%"><tbody><tr>'
                    '<td style="text-align:center">Cell A</td>'
                    '<td style="text-align:right">Cell B</td>'
                    "</tr></tbody></table>"
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<table")
        self.assertContains(response, "color:#ff0000")
        self.assertContains(response, "font-size:18px")
        self.assertContains(response, "font-family:Arial")
        self.assertContains(response, "text-align:center")
        self.assertContains(response, "text-align:right")

    def test_api_posts_returns_paginated_data(self):
        self._create_post(title="API Post")
        response = self.client.get(reverse("blog:api_posts"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("meta", payload)
        self.assertIn("data", payload)
        self.assertGreaterEqual(len(payload["data"]), 1)

    def test_api_posts_respects_public_api_toggle(self):
        self._create_post(title="API Off Post")
        controls = FeatureControlSettings.get_solo()
        controls.enable_public_api = False
        controls.save(update_fields=["enable_public_api", "updated_at"])

        response = self.client.get(reverse("blog:api_posts"))
        self.assertEqual(response.status_code, 403)

    def test_search_suggestions_returns_matching_post(self):
        self._create_post(title="HTMX Search Flow")
        response = self.client.get(
            reverse("blog:search_suggestions"),
            {"q": "htmx"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HTMX Search Flow")

    def test_quick_preview_returns_post_content(self):
        post = self._create_post(title="Quick Preview Post")
        response = self.client.get(
            reverse("blog:post_quick_preview", kwargs={"slug": post.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quick Preview Post")

    def test_quick_preview_respects_feature_toggle(self):
        post = self._create_post(title="Quick Preview Off Post")
        controls = FeatureControlSettings.get_solo()
        controls.enable_quick_preview = False
        controls.save(update_fields=["enable_quick_preview", "updated_at"])

        response = self.client.get(
            reverse("blog:post_quick_preview", kwargs={"slug": post.slug})
        )
        self.assertEqual(response.status_code, 404)

    def test_post_view_uses_session_fingerprint(self):
        post = self._create_post(title="Tracked View Post")

        response = self.client.get(
            reverse("blog:post_detail", kwargs={"slug": post.slug})
        )

        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.views_count, 1)

        view_event = PostView.objects.get(post=post)
        self.assertTrue(view_event.session_key)
        self.assertNotEqual(view_event.session_key, self.client.session.session_key)

    def test_post_view_is_counted_once_per_session(self):
        post = self._create_post(title="Single Count Post")
        detail_url = reverse("blog:post_detail", kwargs={"slug": post.slug})

        self.client.get(detail_url)
        self.client.get(detail_url)

        post.refresh_from_db()
        self.assertEqual(post.views_count, 1)
        self.assertEqual(PostView.objects.filter(post=post).count(), 1)

    def test_post_update_creates_revision(self):
        post = self._create_post(title="Revision Base")
        self.client.login(username="writer", password="strong-password")

        response = self.client.post(
            reverse("blog:post_update", kwargs={"slug": post.slug}),
            {
                "title": "Revision Base Updated",
                "subtitle": "Subtitle",
                "excerpt": "Updated excerpt",
                "body_markdown": "Updated body markdown",
                "meta_title": "Revision Base Updated",
                "meta_description": "Updated description",
                "canonical_url": "",
                "primary_topic": "technology",
                "tags": "django, testing",
                "categories": "technology/django",
                "status": Post.Status.PUBLISHED,
                "is_featured": "on",
                "is_editors_pick": "on",
                "allow_comments": "on",
                "allow_reactions": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertGreaterEqual(post.revisions.count(), 1)

    def test_post_create_rejects_category_depth_over_five(self):
        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:post_create"),
            {
                "title": "Too Deep Categories",
                "subtitle": "",
                "excerpt": "depth test",
                "body_markdown": "Body content",
                "meta_title": "Too Deep Categories",
                "meta_description": "Depth validation",
                "canonical_url": "",
                "primary_topic": "technology",
                "tags": "django,testing",
                "categories": "a/b/c/d/e/f",
                "status": Post.Status.DRAFT,
                "allow_comments": "on",
                "allow_reactions": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Category nesting is limited to 5 levels.")

    def test_post_create_rejects_category_depth_over_configured_limit(self):
        controls = FeatureControlSettings.get_solo()
        controls.category_max_depth = 3
        controls.save(update_fields=["category_max_depth", "updated_at"])

        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:post_create"),
            {
                "title": "Too Deep Categories Configurable",
                "subtitle": "",
                "excerpt": "depth test configurable",
                "body_markdown": "Body content",
                "meta_title": "Too Deep Categories Configurable",
                "meta_description": "Depth validation configurable",
                "canonical_url": "",
                "primary_topic": "technology",
                "tags": "django,testing",
                "categories": "a/b/c/d",
                "status": Post.Status.DRAFT,
                "allow_comments": "on",
                "allow_reactions": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Category nesting is limited to 3 levels.")

    def test_post_create_applies_auto_tags_while_preserving_manual_tags(self):
        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:post_create"),
            {
                "title": "Django HTMX UI patterns",
                "excerpt": "Manual + auto tags workflow",
                "body_markdown": "Django ORM and HTMX partial rendering with Bootstrap UI.",
                "meta_title": "",
                "meta_description": "",
                "canonical_url": "",
                "primary_topic": "",
                "tags": "manualops",
                "categories": "technology/django",
                "status": Post.Status.DRAFT,
                "allow_comments": "on",
                "allow_reactions": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        post = Post.objects.get(title="Django HTMX UI patterns")
        self.assertIn("manualops", [tag.name for tag in post.tags.all()])
        self.assertTrue(post.auto_tags)
        self.assertIsNotNone(post.auto_tagging_updated_at)

    def test_post_create_can_schedule_published_post(self):
        self.client.login(username="writer", password="strong-password")
        scheduled_for = timezone.localtime(timezone.now() + timedelta(days=1, hours=2)).replace(
            second=0,
            microsecond=0,
        )
        response = self.client.post(
            reverse("blog:post_create"),
            {
                "title": "Scheduled Launch Story",
                "excerpt": "Scheduled publication workflow",
                "body_markdown": "This post is scheduled for future publication.",
                "meta_title": "Scheduled Launch Story",
                "meta_description": "Future publication should stay hidden until launch.",
                "canonical_url": "",
                "primary_topic": "technology",
                "tags": "django,scheduling",
                "categories": "technology/django",
                "published_at": scheduled_for.strftime("%Y-%m-%dT%H:%M"),
                "status": Post.Status.PUBLISHED,
                "allow_comments": "on",
                "allow_reactions": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        post = Post.objects.get(title="Scheduled Launch Story")
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(post.published_at)
        self.assertEqual(
            timezone.localtime(post.published_at).strftime("%Y-%m-%dT%H:%M"),
            scheduled_for.strftime("%Y-%m-%dT%H:%M"),
        )

        self.client.logout()
        home = self.client.get(reverse("blog:home"))
        self.assertEqual(home.status_code, 200)
        self.assertNotContains(home, "Scheduled Launch Story")

    def test_auto_tagging_kill_switch_keeps_manual_only_on_update(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_auto_tagging = False
        controls.save(update_fields=["enable_auto_tagging", "updated_at"])

        post = self._create_post(title="Manual only")
        post.auto_tags = ["django", "htmx"]
        post.auto_categories = ["technology/django"]
        post.auto_primary_topic = "technology"
        post.save(
            update_fields=[
                "auto_tags",
                "auto_categories",
                "auto_primary_topic",
            ]
        )

        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:post_update", kwargs={"slug": post.slug}),
            {
                "title": "Manual only updated",
                "excerpt": "Manual tag only mode",
                "body_markdown": "Manual taxonomy mode without algorithmic updates.",
                "meta_title": "",
                "meta_description": "",
                "canonical_url": "",
                "primary_topic": "",
                "tags": "manualtag",
                "categories": "writing/tutorial",
                "status": Post.Status.DRAFT,
                "allow_comments": "on",
                "allow_reactions": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.auto_tags, [])
        self.assertEqual(post.auto_categories, [])
        self.assertEqual(post.auto_primary_topic, "")
        self.assertIsNone(post.auto_tagging_updated_at)
        self.assertIn("manualtag", [tag.name for tag in post.tags.all()])

    def test_auto_tagging_uses_preexisting_tags_from_full_body_content(self):
        seed_post = self._create_post(title="Seed Tag Vocabulary")
        seed_post.tags = "observability"
        seed_post.save()

        self.client.login(username="writer", password="strong-password")
        long_intro = "intro " * 1200
        response = self.client.post(
            reverse("blog:post_create"),
            {
                "title": "Latency diagnostics",
                "excerpt": "Production debugging notes",
                "body_markdown": (
                    f"{long_intro}\n\n"
                    "Final section includes observability tracing metrics logs observability observability."
                ),
                "meta_title": "",
                "meta_description": "",
                "canonical_url": "",
                "primary_topic": "",
                "tags": "manualops",
                "categories": "technology/backend/apis",
                "status": Post.Status.DRAFT,
                "allow_comments": "on",
                "allow_reactions": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get(title="Latency diagnostics")
        self.assertIn("observability", [tag.name for tag in post.tags.all()])

    def test_auto_tagging_respects_total_max_tags_cap(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_auto_tagging = True
        controls.auto_tagging_max_tags = 8
        controls.auto_tagging_max_total_tags = 2
        controls.save(
            update_fields=[
                "enable_auto_tagging",
                "auto_tagging_max_tags",
                "auto_tagging_max_total_tags",
                "updated_at",
            ]
        )

        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:post_create"),
            {
                "title": "Django Python HTMX Alpine Bootstrap Security Performance",
                "excerpt": "Testing API design and postgres optimization",
                "body_markdown": (
                    "django python htmx alpine bootstrap postgres security performance "
                    "api endpoint json rest migration middleware caching."
                ),
                "meta_title": "",
                "meta_description": "",
                "canonical_url": "",
                "primary_topic": "",
                "tags": "manualtag",
                "categories": "technology/django",
                "status": Post.Status.DRAFT,
                "allow_comments": "on",
                "allow_reactions": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get(title="Django Python HTMX Alpine Bootstrap Security Performance")
        self.assertLessEqual(post.tags.count(), 2)

    def test_dashboard_stats_api_includes_tagulous_metrics(self):
        self.client.login(username="writer", password="strong-password")
        self._create_post(title="Tagulous API Post")
        response = self.client.get(reverse("blog:api_dashboard_stats"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("dashboard_tagulous", payload)
        self.assertIn("top_tags", payload["dashboard_tagulous"])
        self.assertIn("top_topics", payload["dashboard_tagulous"])
        self.assertIn("top_categories", payload["dashboard_tagulous"])
        self.assertIn("max_category_depth_live", payload["dashboard_tagulous"])

    def test_author_dashboard_only_lists_own_posts(self):
        other_user = get_user_model().objects.create_user(
            username="other_writer",
            password="strong-password",
        )
        Post.objects.create(
            author=other_user,
            title="Other User Post",
            body_markdown="Other content",
            status=Post.Status.PUBLISHED,
            excerpt="Other excerpt",
        )
        self._create_post(title="Own User Post")

        self.client.login(username="writer", password="strong-password")
        response = self.client.get(reverse("blog:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Own User Post")
        self.assertNotContains(response, "Other User Post")

    def test_staff_dashboard_lists_posts_from_all_authors(self):
        other_user = get_user_model().objects.create_user(
            username="other_writer_all",
            password="strong-password",
        )
        Post.objects.create(
            author=other_user,
            title="Shared Platform Post",
            body_markdown="Shared content",
            status=Post.Status.PUBLISHED,
            excerpt="Shared excerpt",
        )
        staff = get_user_model().objects.create_superuser(
            username="dashboard_staff",
            email="dashboard_staff@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("blog:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shared Platform Post")
        self.assertContains(response, "other_writer_all")

    def test_staff_dashboard_bulk_action_can_manage_other_authors_posts(self):
        other_user = get_user_model().objects.create_user(
            username="other_writer_bulk",
            password="strong-password",
        )
        draft = Post.objects.create(
            author=other_user,
            title="Staff Bulk Publish",
            body_markdown="Draft body",
            status=Post.Status.DRAFT,
            excerpt="Draft excerpt",
        )
        staff = get_user_model().objects.create_superuser(
            username="dashboard_bulk_staff",
            email="dashboard_bulk_staff@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        response = self.client.post(
            reverse("blog:post_bulk_action"),
            {"bulk_action": "publish", "selected_posts": [str(draft.id)]},
        )
        self.assertEqual(response.status_code, 302)
        draft.refresh_from_db()
        self.assertEqual(draft.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(draft.published_at)

    def test_dashboard_posts_are_paginated(self):
        self.client.login(username="writer", password="strong-password")
        for idx in range(15):
            self._create_post(title=f"Paginated Post {idx:02d}")

        first_page = self.client.get(reverse("blog:dashboard"))
        self.assertEqual(first_page.status_code, 200)
        self.assertContains(first_page, "Page 1 of 2")
        self.assertContains(first_page, "Paginated Post 14")
        self.assertNotContains(first_page, "Paginated Post 00")

        second_page = self.client.get(reverse("blog:dashboard"), {"page": 2})
        self.assertEqual(second_page.status_code, 200)
        self.assertContains(second_page, "Page 2 of 2")
        self.assertContains(second_page, "Paginated Post 00")

    def test_dashboard_supports_sort_parameter(self):
        self.client.login(username="writer", password="strong-password")
        self._create_post(title="Zulu Entry")
        self._create_post(title="Alpha Entry")

        response = self.client.get(reverse("blog:dashboard"), {"sort": "title"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="sort"')
        self.assertContains(response, '<option value="title" selected>Title A-Z</option>', html=True)

    def test_project_contract_check_command_passes(self):
        call_command("check_project_contract")

    def test_comment_author_can_update_comment(self):
        post = self._create_post(title="Comment Edit Post")
        comment = Comment.objects.create(post=post, author=self.commenter, body="Original body")

        self.client.login(username="commenter", password="strong-password")
        response = self.client.post(
            reverse("blog:comment_update", kwargs={"comment_id": comment.id}),
            {"body": "Updated body"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.body, "Updated body")

    def test_comment_bulk_action_unapproves_selected_comments(self):
        post = self._create_post(title="Moderation Post")
        c1 = Comment.objects.create(post=post, author=self.commenter, body="First comment")
        c2 = Comment.objects.create(post=post, author=self.commenter, body="Second comment")

        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:comment_bulk_action", kwargs={"slug": post.slug}),
            {
                "bulk_action": "unapprove",
                "selected_comments": [str(c1.id), str(c2.id)],
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertFalse(c1.is_approved)
        self.assertFalse(c2.is_approved)

    def test_comment_create_enters_pending_when_moderation_enabled(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_comments = True
        controls.moderate_comments = True
        controls.save(update_fields=["enable_comments", "moderate_comments", "updated_at"])

        post = self._create_post(title="Moderated Comment Post")
        self.client.login(username="commenter", password="strong-password")

        response = self.client.post(
            reverse("blog:comment_create", kwargs={"slug": post.slug}),
            {"body": "Please review this"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get(post=post, author=self.commenter)
        self.assertFalse(comment.is_approved)
        feedback = self._get_ui_feedback(response)
        self.assertEqual(feedback["toast"]["level"], "info")

    def test_comment_create_enters_pending_when_algorithmic_risk_crosses_threshold(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_comments = True
        controls.moderate_comments = False
        controls.comment_spam_threshold = 20
        controls.save(
            update_fields=[
                "enable_comments",
                "moderate_comments",
                "comment_spam_threshold",
                "updated_at",
            ]
        )

        post = self._create_post(title="Algorithmic Moderation Post")
        self.client.login(username="commenter", password="strong-password")
        response = self.client.post(
            reverse("blog:comment_create", kwargs={"slug": post.slug}),
            {"body": "BUY NOW free money at https://spam.example.com"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get(post=post, author=self.commenter)
        self.assertFalse(comment.is_approved)
        self.assertGreaterEqual(comment.moderation_score, 20)
        self.assertTrue(comment.moderation_reasons)
        feedback = self._get_ui_feedback(response)
        self.assertEqual(feedback["toast"]["level"], "info")
        self.assertIn("risk engine", feedback["toast"]["message"])

    def test_comment_author_can_view_own_pending_comment(self):
        post = self._create_post(title="Pending Visibility Post")
        comment = Comment.objects.create(
            post=post,
            author=self.commenter,
            body="Pending comment body",
            is_approved=False,
        )

        self.client.login(username="commenter", password="strong-password")
        author_response = self.client.get(reverse("blog:post_detail", kwargs={"slug": post.slug}))
        self.assertEqual(author_response.status_code, 200)
        self.assertContains(author_response, comment.body)

        self.client.logout()
        anonymous_response = self.client.get(reverse("blog:post_detail", kwargs={"slug": post.slug}))
        self.assertEqual(anonymous_response.status_code, 200)
        self.assertNotContains(anonymous_response, comment.body)

    def test_comment_create_blocked_when_global_comments_disabled(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_comments = False
        controls.moderate_comments = False
        controls.save(update_fields=["enable_comments", "moderate_comments", "updated_at"])

        post = self._create_post(title="Comments Disabled Post")
        self.client.login(username="commenter", password="strong-password")
        response = self.client.post(
            reverse("blog:comment_create", kwargs={"slug": post.slug}),
            {"body": "Should not be stored"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Comments are disabled globally.", response.content.decode())
        self.assertEqual(Comment.objects.filter(post=post).count(), 0)

    def test_comment_create_htmx_emits_ui_feedback(self):
        post = self._create_post(title="Feedback Post")
        self.client.login(username="commenter", password="strong-password")

        response = self.client.post(
            reverse("blog:comment_create", kwargs={"slug": post.slug}),
            {"body": "Great post!"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        feedback = self._get_ui_feedback(response)
        self.assertEqual(feedback["toast"]["level"], "success")
        self.assertEqual(feedback["inline"]["target"], "comments")

    def test_comment_update_htmx_emits_ui_feedback(self):
        post = self._create_post(title="Comment Update Feedback")
        comment = Comment.objects.create(post=post, author=self.commenter, body="Original")
        self.client.login(username="commenter", password="strong-password")

        response = self.client.post(
            reverse("blog:comment_update", kwargs={"comment_id": comment.id}),
            {"body": "Updated"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        feedback = self._get_ui_feedback(response)
        self.assertEqual(feedback["toast"]["level"], "success")
        self.assertEqual(feedback["inline"]["target"], "comments")

    def test_comment_delete_htmx_emits_ui_feedback(self):
        post = self._create_post(title="Comment Delete Feedback")
        comment = Comment.objects.create(post=post, author=self.commenter, body="Delete me")
        self.client.login(username="commenter", password="strong-password")

        response = self.client.post(
            reverse("blog:comment_delete", kwargs={"comment_id": comment.id}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        feedback = self._get_ui_feedback(response)
        self.assertEqual(feedback["toast"]["level"], "success")
        self.assertEqual(feedback["inline"]["target"], "comments")

    def test_newsletter_subscribe_htmx_emits_ui_feedback_variants(self):
        success_response = self.client.post(
            reverse("blog:newsletter_subscribe"),
            {"email": "feedback@example.com", "full_name": "Feedback User", "company": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(success_response.status_code, 200)
        success_feedback = self._get_ui_feedback(success_response)
        self.assertEqual(success_feedback["toast"]["level"], "success")
        self.assertEqual(success_feedback["inline"]["target"], "newsletter")

        info_response = self.client.post(
            reverse("blog:newsletter_subscribe"),
            {"email": "feedback@example.com", "full_name": "Feedback User", "company": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(info_response.status_code, 200)
        info_feedback = self._get_ui_feedback(info_response)
        self.assertEqual(info_feedback["toast"]["level"], "info")

        error_response = self.client.post(
            reverse("blog:newsletter_subscribe"),
            {"email": "invalid-email", "full_name": "", "company": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(error_response.status_code, 200)
        error_feedback = self._get_ui_feedback(error_response)
        self.assertEqual(error_feedback["toast"]["level"], "error")

    def test_post_bulk_action_archives_selected_posts(self):
        p1 = self._create_post(title="Bulk 1", status=Post.Status.PUBLISHED)
        p2 = self._create_post(title="Bulk 2", status=Post.Status.PUBLISHED)

        self.client.login(username="writer", password="strong-password")
        response = self.client.post(
            reverse("blog:post_bulk_action"),
            {"bulk_action": "archive", "selected_posts": [str(p1.id), str(p2.id)]},
        )
        self.assertEqual(response.status_code, 302)
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p1.status, Post.Status.ARCHIVED)
        self.assertEqual(p2.status, Post.Status.ARCHIVED)

    def test_admin_user_delete_requires_double_verification(self):
        admin_user = get_user_model().objects.create_superuser(
            username="admin_double",
            email="admin_double@example.com",
            password="admin-pass-123",
        )
        target_user = get_user_model().objects.create_user(
            username="delete_me",
            password="strong-password",
        )

        self.client.force_login(admin_user)
        changelist_url = reverse("admin:auth_user_changelist")

        step_one = self.client.post(
            changelist_url,
            {
                "action": "delete_users_double_check",
                ACTION_CHECKBOX_NAME: [str(target_user.id)],
            },
        )
        self.assertEqual(step_one.status_code, 200)
        self.assertContains(step_one, "Double Verification Required")

        step_two = self.client.post(
            changelist_url,
            {
                "action": "delete_users_double_check",
                ACTION_CHECKBOX_NAME: [str(target_user.id)],
                "confirmation_phrase": "DELETE USERS",
                "confirm_count": "1",
                "double_check": "on",
                "confirm_delete": "1",
            },
        )
        self.assertEqual(step_two.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(username="delete_me").exists())

    def test_admin_dashboard_shows_overview_cards_for_staff(self):
        self._create_post(title="Admin Metrics Post")
        staff = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Site Overview")
        self.assertContains(response, "Repo Overview")
        self.assertContains(response, "Performance Snapshot (7d)")

    def test_admin_navigation_hides_newsletter_model(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_nav",
            email="admin_nav@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Newsletter subscribers")

    def test_admin_blog_menu_shows_primary_topics_and_categories(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_blog_nav",
            email="admin_blog_nav@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blog")
        self.assertContains(response, "Posts")
        self.assertContains(response, "Categories")
        self.assertContains(response, "Primary Topics")
        self.assertContains(response, "Tags")
        self.assertContains(response, "Comments")

    def test_admin_sidebar_badges_show_live_counts(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_badges",
            email="admin_badges@example.com",
            password="admin-pass-123",
        )
        post = self._create_post(title="Badge Post")
        Comment.objects.create(
            post=post,
            author=self.commenter,
            body="Pending moderation",
            is_approved=False,
        )

        cache.clear()
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<span class="nav-badge">1</span>', html=True)
        self.assertNotContains(response, '<span class="nav-badge">5</span>', html=True)
        self.assertNotContains(response, '<span class="nav-badge">12</span>', html=True)

    def test_custom_admin_posts_bulk_action_publishes_selected_posts(self):
        post = self._create_post(title="Admin Bulk Draft", status=Post.Status.DRAFT)
        staff = get_user_model().objects.create_superuser(
            username="admin_bulk_posts",
            email="admin_bulk_posts@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("blog:admin_posts_bulk_action"),
            {"bulk_action": "publish", "selected_posts": [str(post.id)]},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(post.published_at)

    def test_custom_admin_comment_approve_htmx_returns_workspace_item(self):
        post = self._create_post(title="Moderation Item")
        comment = Comment.objects.create(
            post=post,
            author=self.commenter,
            body="Needs review",
            is_approved=False,
        )
        Comment.objects.create(
            post=post,
            author=self.commenter,
            body="Still pending",
            is_approved=False,
        )
        staff = get_user_model().objects.create_superuser(
            username="admin_comment_moderator",
            email="admin_comment_moderator@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("blog:admin_comment_approve", kwargs={"comment_id": comment.id}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.commenter.username)
        self.assertContains(response, "Comment approved.")
        self.assertContains(response, 'id="admin-messages"')
        self.assertContains(response, 'id="admin-comments-nav-badge"')
        self.assertContains(response, "hx-swap-oob=\"outerHTML\"")
        self.assertContains(response, '<span class="nav-badge">1</span>', html=True)
        comment.refresh_from_db()
        self.assertTrue(comment.is_approved)

    def test_custom_admin_comments_list_filters_by_post_and_sort(self):
        post_one = self._create_post(title="Filter Target One")
        post_two = self._create_post(title="Filter Target Two")
        Comment.objects.create(post=post_one, author=self.commenter, body="Comment for one")
        Comment.objects.create(post=post_two, author=self.commenter, body="Comment for two")
        staff = get_user_model().objects.create_superuser(
            username="admin_comment_filter",
            email="admin_comment_filter@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.get(
            reverse("blog:admin_comments_list"),
            {"post": str(post_one.id), "sort": "created_at"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comment for one")
        self.assertNotContains(response, "Comment for two")

    def test_custom_admin_comments_bulk_action_approves_selected(self):
        post = self._create_post(title="Comment Bulk Moderation")
        comment = Comment.objects.create(
            post=post,
            author=self.commenter,
            body="Pending bulk moderation",
            is_approved=False,
        )
        staff = get_user_model().objects.create_superuser(
            username="admin_comment_bulk",
            email="admin_comment_bulk@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("blog:admin_comments_bulk_action"),
            {
                "bulk_action": "approve",
                "selected_comments": [str(comment.id)],
                "next_url": reverse("admin_comments_list"),
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Redirect"), reverse("admin_comments_list"))
        comment.refresh_from_db()
        self.assertTrue(comment.is_approved)

    def test_custom_admin_pages_bulk_action_publishes_selected(self):
        page = Page.objects.create(
            author=self.user,
            title="Bulk Managed Page",
            body_markdown="Page body",
            status=Page.Status.DRAFT,
        )
        staff = get_user_model().objects.create_superuser(
            username="admin_page_bulk",
            email="admin_page_bulk@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("admin_pages_bulk_action"),
            {
                "bulk_action": "publish",
                "selected_pages": [str(page.id)],
                "next_url": reverse("admin_pages_list"),
            },
        )
        self.assertEqual(response.status_code, 302)
        page.refresh_from_db()
        self.assertEqual(page.status, Page.Status.PUBLISHED)
        self.assertIsNotNone(page.published_at)

    def test_custom_admin_users_bulk_action_deactivates_selected(self):
        target_user = get_user_model().objects.create_user(
            username="bulk_target_user",
            email="bulk_target_user@example.com",
            password="strong-password",
            is_active=True,
        )
        staff = get_user_model().objects.create_superuser(
            username="admin_user_bulk",
            email="admin_user_bulk@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("admin_users_bulk_action"),
            {
                "bulk_action": "deactivate",
                "selected_users": [str(target_user.id)],
                "next_url": reverse("admin_users_list"),
            },
        )
        self.assertEqual(response.status_code, 302)
        target_user.refresh_from_db()
        self.assertFalse(target_user.is_active)

    def test_custom_admin_tags_bulk_action_protects_selected(self):
        tag_model = Post.tags.tag_model
        tag = tag_model.objects.create(name="bulk-tag")
        staff = get_user_model().objects.create_superuser(
            username="admin_tag_bulk",
            email="admin_tag_bulk@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("admin_tags_bulk_action"),
            {
                "bulk_action": "protect",
                "selected_tags": [str(tag.id)],
                "next_url": reverse("admin_tags_list"),
            },
        )
        self.assertEqual(response.status_code, 302)
        tag.refresh_from_db()
        self.assertTrue(tag.protected)

    def test_admin_settings_persists_comment_controls(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_settings_comments",
            email="admin_settings_comments@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("blog:admin_settings"),
            {"allow_comments": "on", "moderate_comments": "on", "spam_threshold": "90"},
        )
        self.assertEqual(response.status_code, 302)
        controls = FeatureControlSettings.get_solo()
        self.assertTrue(controls.enable_comments)
        self.assertTrue(controls.moderate_comments)
        self.assertEqual(controls.comment_spam_threshold, 90)

    def test_admin_settings_persists_appearance_branding_and_platform_controls(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_settings_full",
            email="admin_settings_full@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("blog:admin_settings"),
            {
                "theme_mode": "dark",
                "theme_preset": "evergreen",
                "site_name": "Unified Platform",
                "admin_brand_name": "Unified Admin",
                "brand_logo_url": "https://cdn.example.com/logo-light.svg",
                "brand_logo_dark_url": "https://cdn.example.com/logo-dark.svg",
                "favicon_url": "https://cdn.example.com/favicon-light.svg",
                "favicon_dark_url": "https://cdn.example.com/favicon-dark.svg",
                "site_tagline": "One source of truth",
                "default_author_display": "Editorial Team",
                "support_email": "support@example.com",
                "contact_email": "contact@example.com",
                "footer_notice": "All rights reserved.",
                "legal_company_name": "Unified Labs",
                "homepage_cta_label": "Start",
                "homepage_cta_url": "/",
                "allow_comments": "on",
                "moderate_comments": "on",
                "spam_threshold": "80",
                "enable_newsletter": "on",
                "enable_reactions": "on",
                "enable_quick_preview": "on",
                "enable_public_api": "on",
                "enable_policy_pages": "on",
                "enable_sitemap": "on",
                "enable_user_registration": "on",
                "enable_auto_tagging": "on",
                "auto_tagging_max_tags": "8",
                "auto_tagging_max_total_tags": "16",
                "auto_tagging_max_categories": "4",
                "category_max_depth": "7",
                "auto_tagging_min_score": "1.5",
                "analytics_provider": "ga4",
                "ga4_measurement_id": "G-TEST1234",
                "webhook_url": "https://hooks.example.com/djangoblog",
                "webhook_secret": "super-secret",
                "smtp_sender_name": "Ops Team",
                "smtp_sender_email": "ops@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)

        appearance = SiteAppearanceSettings.get_solo()
        identity = SiteIdentitySettings.get_solo()
        controls = FeatureControlSettings.get_solo()
        integrations = IntegrationSettings.get_solo()

        self.assertEqual(appearance.mode, SiteAppearanceSettings.Mode.DARK)
        self.assertEqual(appearance.preset, "evergreen")
        self.assertEqual(identity.site_name, "Unified Platform")
        self.assertEqual(identity.admin_brand_name, "Unified Admin")
        self.assertEqual(identity.brand_logo_url, "https://cdn.example.com/logo-light.svg")
        self.assertEqual(identity.brand_logo_dark_url, "https://cdn.example.com/logo-dark.svg")
        self.assertEqual(identity.favicon_url, "https://cdn.example.com/favicon-light.svg")
        self.assertEqual(identity.favicon_dark_url, "https://cdn.example.com/favicon-dark.svg")
        self.assertEqual(identity.site_tagline, "One source of truth")
        self.assertTrue(controls.enable_comments)
        self.assertTrue(controls.moderate_comments)
        self.assertTrue(controls.enable_newsletter)
        self.assertTrue(controls.enable_reactions)
        self.assertEqual(controls.auto_tagging_max_tags, 8)
        self.assertEqual(controls.auto_tagging_max_total_tags, 16)
        self.assertEqual(controls.auto_tagging_max_categories, 4)
        self.assertEqual(controls.category_max_depth, 7)
        self.assertAlmostEqual(controls.auto_tagging_min_score, 1.5)
        self.assertEqual(integrations.analytics_provider, "ga4")
        self.assertEqual(integrations.ga4_measurement_id, "G-TEST1234")
        self.assertEqual(integrations.smtp_sender_email, "ops@example.com")

    def test_admin_settings_seo_sections_link_to_seo_control_workspace(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_settings_seo_workspace",
            email="admin_settings_seo_workspace@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("blog:admin_settings"), {"section": "seo"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse(
                "admin_config:seo_control_canonical_section",
                kwargs={"section": "settings"},
            ),
        )
        self.assertNotContains(response, 'name="default_meta_title"')
        self.assertNotContains(response, 'name="google_site_verification"')

    def test_admin_theme_toggle_endpoint_updates_global_mode(self):
        appearance = SiteAppearanceSettings.get_solo()
        appearance.mode = SiteAppearanceSettings.Mode.LIGHT
        appearance.save(update_fields=["mode", "updated_at"])

        staff = get_user_model().objects.create_superuser(
            username="admin_toggle_theme",
            email="admin_toggle_theme@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        response = self.client.post(reverse("blog:admin_settings_theme_toggle"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "dark")
        self.assertIn("css_variables", response.json())
        appearance.refresh_from_db()
        self.assertEqual(appearance.mode, SiteAppearanceSettings.Mode.DARK)

    def test_api_appearance_state_returns_live_mode_and_preset(self):
        appearance = SiteAppearanceSettings.get_solo()
        appearance.mode = SiteAppearanceSettings.Mode.DARK
        appearance.preset = "evergreen"
        appearance.save(update_fields=["mode", "preset", "updated_at"])

        response = self.client.get(reverse("blog:api_appearance_state"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "dark")
        self.assertEqual(payload["preset"], "evergreen")
        self.assertIn("css_variables", payload)
        self.assertIn("--brand", payload["css_variables"])
        self.assertIn("updated_at", payload)

    def test_home_cards_render_live_reaction_controls(self):
        post = self._create_post(title="Card Reaction Post")
        self.client.login(username="commenter", password="strong-password")

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="post-reaction-{post.id}"')
        self.assertContains(response, reverse("blog:toggle_like", kwargs={"slug": post.slug}))
        self.assertContains(response, 'name="reaction_context" value="card"')

    def test_toggle_like_card_context_returns_card_partial(self):
        post = self._create_post(title="Card Toggle Like Post")
        self.client.login(username="commenter", password="strong-password")

        response = self.client.post(
            reverse("blog:toggle_like", kwargs={"slug": post.slug}),
            {"reaction_context": "card"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="post-reaction-{post.id}"')
        self.assertNotContains(response, 'id="reaction-bar"')
        self.assertTrue(PostLike.objects.filter(post=post, user=self.commenter).exists())

    def test_toggle_like_blocked_when_global_reactions_disabled(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_reactions = False
        controls.save(update_fields=["enable_reactions", "updated_at"])

        post = self._create_post(title="Global Reactions Off")
        self.client.login(username="commenter", password="strong-password")
        response = self.client.post(
            reverse("blog:toggle_like", kwargs={"slug": post.slug}),
            {"reaction_context": "card"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Reactions are disabled globally.", response.content.decode())
        self.assertFalse(PostLike.objects.filter(post=post, user=self.commenter).exists())

    def test_home_brand_logo_uses_identity_logo_url(self):
        identity = SiteIdentitySettings.get_solo()
        identity.brand_logo_url = "https://cdn.example.com/brand-light.svg"
        identity.brand_logo_dark_url = "https://cdn.example.com/brand-dark.svg"
        identity.save(update_fields=["brand_logo_url", "brand_logo_dark_url", "updated_at"])

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-theme-logo')
        self.assertContains(response, "https://cdn.example.com/brand-light.svg")
        self.assertContains(response, "https://cdn.example.com/brand-dark.svg")

    def test_base_template_uses_configured_favicon_urls(self):
        identity = SiteIdentitySettings.get_solo()
        identity.favicon_url = "https://cdn.example.com/favicon-light.svg"
        identity.favicon_dark_url = "https://cdn.example.com/favicon-dark.svg"
        identity.save(update_fields=["favicon_url", "favicon_dark_url", "updated_at"])

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://cdn.example.com/favicon-light.svg")
        self.assertContains(response, "https://cdn.example.com/favicon-dark.svg")

    def test_admin_changelist_pages_load_core_partialization_script(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_hx_changelist",
            email="admin_hx_changelist@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/admin/core.js")
        self.assertContains(response, 'id="changelist"')

    def test_default_admin_changelist_pages_render_partializable_module(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_changelist_targets",
            email="admin_changelist_targets@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        urls = [
            reverse("admin:auth_user_changelist"),
            reverse("admin:auth_group_changelist"),
            reverse("admin:pages_page_changelist"),
            reverse("admin:blog_tagulous_post_tags_changelist"),
            reverse("admin:blog_tagulous_post_categories_changelist"),
            reverse("admin:blog_tagulous_post_primary_topic_changelist"),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'id="changelist"')

    def test_tagulous_admin_add_pages_render_without_slug_keyerror(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_tagulous_add_pages",
            email="admin_tagulous_add_pages@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        add_urls = [
            reverse("admin:blog_tagulous_post_tags_add"),
            reverse("admin:blog_tagulous_post_primary_topic_add"),
            reverse("admin:blog_tagulous_post_categories_add"),
        ]
        for url in add_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'id="tagulous')  # tagulous widget payload exists

    def test_custom_admin_workspace_routes_render_unified_workspace_shell(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_workspace_routes",
            email="admin_workspace_routes@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        urls = [
            reverse("admin_pages_list"),
            reverse("admin_tags_list"),
            reverse("admin_categories_list"),
            reverse("admin_topics_list"),
            reverse("admin_users_list"),
            reverse("admin_groups_list"),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "workspace-shell")
            self.assertContains(response, "workspace-kpis")
            self.assertContains(response, "workspace-filter-grid")

    def test_custom_admin_workspace_routes_return_htmx_table_partials(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_workspace_hx",
            email="admin_workspace_hx@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        urls = [
            reverse("admin_pages_list"),
            reverse("admin_tags_list"),
            reverse("admin_categories_list"),
            reverse("admin_topics_list"),
            reverse("admin_users_list"),
            reverse("admin_groups_list"),
        ]
        for url in urls:
            response = self.client.get(url, HTTP_HX_REQUEST="true")
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "workspace-table-card")
            self.assertNotContains(response, "<html")

    def test_admin_categories_reparent_moves_branch_under_target_parent(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_categories_reparent",
            email="admin_categories_reparent@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        category_model = Post.categories.tag_model
        target_parent = category_model.objects.create(name="technology")
        moving = category_model.objects.create(name="writing")
        moving_child = category_model.objects.create(name="writing/tutorial")

        response = self.client.post(
            reverse("admin_categories_reparent"),
            {"category_id": moving.id, "parent_id": target_parent.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        moving.refresh_from_db()
        moving_child.refresh_from_db()
        self.assertEqual(moving.name, "technology/writing")
        self.assertEqual(moving.parent_id, target_parent.id)
        self.assertEqual(moving_child.name, "technology/writing/tutorial")

    def test_admin_categories_reparent_rejects_descendant_parent(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_categories_cycle",
            email="admin_categories_cycle@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        category_model = Post.categories.tag_model
        root = category_model.objects.create(name="root")
        child = category_model.objects.create(name="root/child")

        response = self.client.post(
            reverse("admin_categories_reparent"),
            {"category_id": root.id, "parent_id": child.id},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertIn("descendant", response.json()["message"].lower())

    def test_admin_categories_reparent_respects_configured_max_depth(self):
        controls = FeatureControlSettings.get_solo()
        controls.category_max_depth = 2
        controls.save(update_fields=["category_max_depth", "updated_at"])

        staff = get_user_model().objects.create_superuser(
            username="admin_categories_depth_guard",
            email="admin_categories_depth_guard@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        category_model = Post.categories.tag_model
        deep_parent = category_model.objects.create(name="a/b")
        moving = category_model.objects.create(name="x")

        response = self.client.post(
            reverse("admin_categories_reparent"),
            {"category_id": moving.id, "parent_id": deep_parent.id},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertIn("max category depth", response.json()["message"].lower())

    def test_custom_admin_workspace_uses_unified_pagination_size(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_workspace_pagesize",
            email="admin_workspace_pagesize@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        for index in range(21):
            get_user_model().objects.create_user(
                username=f"pager_user_{index:02d}",
                password="strong-password",
            )

        urls = [
            reverse("admin_posts_list"),
            reverse("admin_comments_list"),
            reverse("admin_pages_list"),
            reverse("admin_tags_list"),
            reverse("admin_categories_list"),
            reverse("admin_topics_list"),
            reverse("admin_users_list"),
            reverse("admin_groups_list"),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["page_obj"].paginator.per_page, ADMIN_PAGINATION_SIZE)

        first_page = self.client.get(
            reverse("admin_users_list"),
            {"search": "pager_user_"},
        )
        self.assertEqual(first_page.status_code, 200)
        self.assertContains(first_page, "Page 1 of 2")
        self.assertEqual(len(first_page.context["users"]), ADMIN_PAGINATION_SIZE)

        second_page = self.client.get(
            reverse("admin_users_list"),
            {"search": "pager_user_", "page": 2},
        )
        self.assertEqual(second_page.status_code, 200)
        self.assertContains(second_page, "Page 2 of 2")
        self.assertEqual(len(second_page.context["users"]), 1)

    def test_custom_admin_post_editor_applies_status_and_taxonomy(self):
        post = self._create_post(title="Workspace Draft", status=Post.Status.DRAFT)
        staff = get_user_model().objects.create_superuser(
            username="admin_editor",
            email="admin_editor@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("blog:admin_post_editor", kwargs={"post_id": post.id}),
            {
                "title": "Workspace Draft Updated",
                "slug": post.slug,
                "excerpt": "Updated excerpt",
                "body_markdown": "django htmx taxonomy workflow update",
                "meta_title": "Workspace Draft Updated",
                "meta_description": "Updated through custom workspace editor",
                "canonical_url": "",
                "primary_topic": "technology",
                "tags": "django,workflow",
                "categories": "technology/django",
                "allow_comments": "on",
                "allow_reactions": "on",
                "action": "published",
            },
        )
        self.assertEqual(response.status_code, 302)

        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(post.published_at)
        self.assertIn("django", [tag.name for tag in post.tags.all()])
        self.assertIn("workflow", [tag.name for tag in post.tags.all()])
        self.assertIn("technology/django", [tag.name for tag in post.categories.all()])
        self.assertEqual(post.primary_topic.name if post.primary_topic else "", "technology")
        self.assertIsNotNone(post.auto_tagging_updated_at)

    def test_custom_admin_post_editor_can_schedule_future_publish(self):
        post = self._create_post(title="Workspace Scheduled", status=Post.Status.DRAFT)
        staff = get_user_model().objects.create_superuser(
            username="admin_editor_schedule",
            email="admin_editor_schedule@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        scheduled_for = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
            second=0,
            microsecond=0,
        )
        response = self.client.post(
            reverse("blog:admin_post_editor", kwargs={"post_id": post.id}),
            {
                "title": "Workspace Scheduled Updated",
                "slug": post.slug,
                "excerpt": "Updated excerpt",
                "body_markdown": "scheduled workflow body",
                "meta_title": "Workspace Scheduled Updated",
                "meta_description": "Scheduled through custom workspace editor",
                "canonical_url": "",
                "primary_topic": "technology",
                "tags": "django,workflow",
                "categories": "technology/django",
                "publish_at": scheduled_for.strftime("%Y-%m-%dT%H:%M"),
                "allow_comments": "on",
                "allow_reactions": "on",
                "action": "published",
            },
        )
        self.assertEqual(response.status_code, 302)

        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(post.published_at)
        self.assertEqual(
            timezone.localtime(post.published_at).strftime("%Y-%m-%dT%H:%M"),
            scheduled_for.strftime("%Y-%m-%dT%H:%M"),
        )

    def test_custom_admin_post_editor_rejects_invalid_publish_schedule(self):
        post = self._create_post(title="Workspace Invalid Schedule", status=Post.Status.DRAFT)
        staff = get_user_model().objects.create_superuser(
            username="admin_editor_invalid_schedule",
            email="admin_editor_invalid_schedule@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("blog:admin_post_editor", kwargs={"post_id": post.id}),
            {
                "title": "Workspace Invalid Schedule Updated",
                "slug": post.slug,
                "body_markdown": "body",
                "publish_at": "invalid-datetime",
                "action": "published",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Invalid publish schedule", status_code=400)

    def test_custom_admin_post_editor_keeps_save_when_taxonomy_sync_fails(self):
        post = self._create_post(title="Workspace Taxonomy Fail", status=Post.Status.DRAFT)
        staff = get_user_model().objects.create_superuser(
            username="admin_editor_tax_fail",
            email="admin_editor_tax_fail@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        with patch("blog.admin_views.apply_auto_taxonomy_to_post", side_effect=RuntimeError("tax failure")):
            response = self.client.post(
                reverse("blog:admin_post_editor", kwargs={"post_id": post.id}),
                {
                    "title": "Workspace Taxonomy Fail Updated",
                    "slug": post.slug,
                    "body_markdown": "body",
                    "action": "draft",
                },
            )
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.title, "Workspace Taxonomy Fail Updated")
        self.assertEqual(post.status, Post.Status.DRAFT)

    def test_post_create_succeeds_even_when_auto_taxonomy_fails(self):
        self.client.login(username="writer", password="strong-password")
        with patch("blog.views.apply_auto_taxonomy_to_post", side_effect=RuntimeError("auto taxonomy failure")):
            response = self.client.post(
                reverse("blog:post_create"),
                {
                    "title": "Create With Taxonomy Warning",
                    "excerpt": "Taxonomy warning path",
                    "body_markdown": "content",
                    "meta_title": "Create With Taxonomy Warning",
                    "meta_description": "Taxonomy warning path should still save",
                    "canonical_url": "",
                    "primary_topic": "technology",
                    "tags": "django",
                    "categories": "technology/django",
                    "status": Post.Status.DRAFT,
                    "allow_comments": "on",
                    "allow_reactions": "on",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Post.objects.filter(title="Create With Taxonomy Warning").exists())

    def test_custom_admin_post_editor_rejects_categories_over_configured_depth(self):
        controls = FeatureControlSettings.get_solo()
        controls.category_max_depth = 3
        controls.save(update_fields=["category_max_depth", "updated_at"])

        post = self._create_post(title="Workspace Depth Guard", status=Post.Status.DRAFT)
        staff = get_user_model().objects.create_superuser(
            username="admin_editor_depth",
            email="admin_editor_depth@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("blog:admin_post_editor", kwargs={"post_id": post.id}),
            {
                "title": "Workspace Depth Guard",
                "slug": post.slug,
                "body_markdown": "body",
                "categories": "a/b/c/d",
                "action": "draft",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response,
            "Category nesting is limited to 3 levels.",
            status_code=400,
        )

    def test_group_admin_changelist_renders_with_custom_admin_class(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_groups",
            email="admin_groups@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:auth_group_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Roles & Permissions")

    def test_base_template_uses_admin_selected_strict_theme(self):
        appearance = SiteAppearanceSettings.get_solo()
        appearance.mode = SiteAppearanceSettings.Mode.DARK
        appearance.preset = "evergreen"
        appearance.save(update_fields=["mode", "preset", "updated_at"])

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-theme="dark"')
        self.assertContains(response, "--brand: #3ad3a1;")

    def test_admin_base_template_uses_global_appearance_mode(self):
        appearance = SiteAppearanceSettings.get_solo()
        appearance.mode = SiteAppearanceSettings.Mode.LIGHT
        appearance.save(update_fields=["mode", "updated_at"])

        staff = get_user_model().objects.create_superuser(
            username="admin_theme_mode",
            email="admin_theme_mode@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-theme="light"')

    def test_admin_base_template_includes_bootstrap_bundle(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_bootstrap_bundle",
            email="admin_bootstrap_bundle@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bootstrap.bundle.min.js")

    def test_base_template_emits_site_ownership_meta_tags(self):
        seo_defaults = SeoSettings.get_solo()
        seo_defaults.google_site_verification = "google-meta-token"
        seo_defaults.bing_site_verification = "bing-meta-token"
        seo_defaults.yandex_site_verification = "yandex-meta-token"
        seo_defaults.pinterest_site_verification = "pin-meta-token"
        seo_defaults.save(
            update_fields=[
                "google_site_verification",
                "bing_site_verification",
                "yandex_site_verification",
                "pinterest_site_verification",
                "updated_at",
            ]
        )

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="google-site-verification"')
        self.assertContains(response, 'name="msvalidate.01"')
        self.assertContains(response, 'name="yandex-verification"')
        self.assertContains(response, 'name="p:domain_verify"')

    def test_base_template_honors_social_meta_feature_flags(self):
        seo_defaults = SeoSettings.get_solo()
        seo_defaults.enable_open_graph = False
        seo_defaults.enable_twitter_cards = False
        seo_defaults.save(
            update_fields=["enable_open_graph", "enable_twitter_cards", "updated_at"]
        )

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'property="og:title"')
        self.assertNotContains(response, 'name="twitter:card"')

    def test_base_template_renders_ga4_script_when_integration_enabled(self):
        integrations = IntegrationSettings.get_solo()
        integrations.analytics_provider = IntegrationSettings.AnalyticsProvider.GA4
        integrations.ga4_measurement_id = "G-UNITTEST123"
        integrations.save(update_fields=["analytics_provider", "ga4_measurement_id", "updated_at"])

        response = self.client.get(reverse("blog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "googletagmanager.com/gtag/js")
        self.assertContains(response, "G-UNITTEST123")

    def test_admin_dashboard_shows_appearance_studio_card(self):
        staff = get_user_model().objects.create_superuser(
            username="admin_theme",
            email="admin_theme@example.com",
            password="admin-pass-123",
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Appearance Studio")


class UiFeedbackHelperTests(TestCase):
    def test_attach_ui_feedback_sets_hx_trigger_payload(self):
        response = HttpResponse("ok")
        attach_ui_feedback(
            response,
            toast={"level": "success", "message": "Saved"},
            inline={"target": "comments", "level": "success", "message": "Saved"},
        )

        payload = json.loads(response.headers["HX-Trigger"])
        self.assertIn("ui:feedback", payload)
        self.assertEqual(payload["ui:feedback"]["toast"]["level"], "success")
        self.assertEqual(payload["ui:feedback"]["inline"]["target"], "comments")

    def test_attach_ui_feedback_merges_existing_hx_trigger(self):
        response = HttpResponse("ok")
        response.headers["HX-Trigger"] = json.dumps({"existing:event": {"status": "ok"}})

        attach_ui_feedback(
            response,
            toast={"level": "info", "message": "Done"},
            inline={"target": "global", "level": "info", "message": "Done"},
        )

        payload = json.loads(response.headers["HX-Trigger"])
        self.assertIn("existing:event", payload)
        self.assertIn("ui:feedback", payload)


class UiInteractionTemplateTests(TestCase):
    def test_no_browser_native_confirm_calls_remain_in_templates(self):
        template_paths = [
            Path("templates/blog/partials/comment_list.html"),
            Path("templates/blog/partials/comments_section.html"),
            Path("templates/blog/partials/reaction_bar.html"),
            Path("templates/blog/dashboard.html"),
            Path("templates/pages/page_manage.html"),
            Path("templates/blog/post_form.html"),
            Path("templates/pages/page_form.html"),
        ]
        for path in template_paths:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("confirm(", content, msg=f"Native confirm found in {path}")

    def test_mutation_templates_include_ui_contract_attributes(self):
        checks = {
            "templates/blog/partials/comment_list.html": [
                'hx-confirm="Delete this comment?"',
                'data-ui-feedback-target="comments"',
                'data-ui-action-kind="delete"',
            ],
            "templates/blog/partials/comments_section.html": [
                'hx-confirm="Post this comment?"',
                'data-ui-action-kind="create"',
            ],
            "templates/blog/partials/reaction_bar.html": [
                'data-ui-feedback-target="reactions"',
                'data-ui-action-kind="toggle"',
            ],
            "templates/blog/dashboard.html": [
                'data-ui-confirm-template=\'Apply "{action}" to selected posts?\'',
                'data-ui-feedback-slot="dashboard-posts"',
            ],
            "templates/pages/page_manage.html": [
                'data-ui-confirm-template=\'Apply "{action}" to selected pages?\'',
                'data-ui-feedback-slot="pages-manage"',
            ],
            "templates/blog/post_form.html": [
                'data-ui-feedback-target="post-form"',
                'data-ui-action-kind="{% if mode == \'Create\' %}create{% else %}update{% endif %}"',
            ],
            "templates/pages/page_form.html": [
                'data-ui-feedback-target="page-form"',
                'data-ui-action-kind="{% if mode == \'Create\' %}create{% else %}update{% endif %}"',
            ],
        }

        for file_path, required_snippets in checks.items():
            content = Path(file_path).read_text(encoding="utf-8")
            for snippet in required_snippets:
                self.assertIn(snippet, content, msg=f"Missing '{snippet}' in {file_path}")
