from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blog.models import Post
from core.models import FeatureControlSettings

from .models import Page


class PageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="page_writer",
            password="strong-password",
        )

    def _create_page(self, title="Page", status=Page.Status.PUBLISHED):
        return Page.objects.create(
            author=self.user,
            title=title,
            summary="Page summary",
            body_markdown="# Heading\n\nPage body",
            status=status,
        )

    def test_page_slug_and_html_generated(self):
        page = self._create_page(title="Ultimate Docs Page")
        self.assertTrue(page.slug.startswith("ultimate-docs-page"))
        self.assertIn("<h1>", page.body_html)
        self.assertGreater(page.word_count, 0)

    def test_page_detail_hides_drafts_from_anonymous(self):
        draft = self._create_page(title="Draft Page", status=Page.Status.DRAFT)
        public = self._create_page(title="Public Page", status=Page.Status.PUBLISHED)

        draft_response = self.client.get(reverse("pages:detail", kwargs={"slug": draft.slug}))
        public_response = self.client.get(reverse("pages:detail", kwargs={"slug": public.slug}))

        self.assertEqual(draft_response.status_code, 404)
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, "Public Page")

    def test_page_detail_includes_algorithmic_related_pages_panel(self):
        anchor = self._create_page(title="Django Documentation Guide")
        related = self._create_page(title="Django Deployment Checklist")

        response = self.client.get(reverse("pages:detail", kwargs={"slug": anchor.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Related Pages")
        self.assertContains(response, related.title)

    def test_page_create_records_revision(self):
        self.client.login(username="page_writer", password="strong-password")

        response = self.client.post(
            reverse("pages:create"),
            {
                "title": "Team Page",
                "slug": "",
                "nav_label": "Team",
                "summary": "About the team",
                "body_markdown": "# Team\n\nAll details",
                "template_key": Page.TemplateKey.DEFAULT,
                "show_in_navigation": "on",
                "nav_order": 5,
                "is_featured": "on",
                "meta_title": "Team",
                "meta_description": "Team page",
                "canonical_url": "",
                "status": Page.Status.PUBLISHED,
                "published_at": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        page = Page.objects.get(title="Team Page")
        self.assertGreaterEqual(page.revisions.count(), 1)

    def test_pages_api_returns_data(self):
        self._create_page(title="API Page", status=Page.Status.PUBLISHED)
        response = self.client.get(reverse("pages:api_pages"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("meta", payload)
        self.assertIn("data", payload)
        self.assertGreaterEqual(len(payload["data"]), 1)

    def test_pages_api_respects_public_api_toggle(self):
        self._create_page(title="API Toggle Page", status=Page.Status.PUBLISHED)
        controls = FeatureControlSettings.get_solo()
        controls.enable_public_api = False
        controls.save(update_fields=["enable_public_api", "updated_at"])

        response = self.client.get(reverse("pages:api_pages"))
        self.assertEqual(response.status_code, 403)

    def test_page_bulk_action_updates_selected_pages(self):
        p1 = self._create_page(title="Bulk Page 1", status=Page.Status.DRAFT)
        p2 = self._create_page(title="Bulk Page 2", status=Page.Status.DRAFT)

        self.client.login(username="page_writer", password="strong-password")
        response = self.client.post(
            reverse("pages:bulk_action"),
            {
                "bulk_action": "nav_on",
                "selected_pages": [str(p1.id), str(p2.id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(p1.show_in_navigation)
        self.assertTrue(p2.show_in_navigation)

    def test_policy_index_and_detail_render(self):
        index_response = self.client.get(reverse("pages:policy_index"))
        self.assertEqual(index_response.status_code, 200)
        self.assertContains(index_response, "Policy Center")
        self.assertContains(index_response, "Privacy Policy")

        detail_response = self.client.get(
            reverse("pages:policy_detail", kwargs={"slug": "privacy-policy"})
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Privacy Policy")
        self.assertContains(detail_response, "Information We Collect")

    def test_policy_routes_respect_feature_toggle(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_policy_pages = False
        controls.save(update_fields=["enable_policy_pages", "updated_at"])

        index_response = self.client.get(reverse("pages:policy_index"))
        detail_response = self.client.get(
            reverse("pages:policy_detail", kwargs={"slug": "privacy-policy"})
        )
        self.assertEqual(index_response.status_code, 404)
        self.assertEqual(detail_response.status_code, 404)

    def test_policy_detail_uses_page_override_when_available(self):
        Page.objects.create(
            author=self.user,
            title="Custom Privacy Policy",
            slug="privacy-policy",
            summary="Custom summary",
            body_markdown="# Custom Policy\n\nCustom privacy content.",
            status=Page.Status.PUBLISHED,
        )

        response = self.client.get(
            reverse("pages:policy_detail", kwargs={"slug": "privacy-policy"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Custom Privacy Policy")
        self.assertContains(response, "Custom privacy content.")

    def test_sitemap_and_xslt_endpoints(self):
        post = Post.objects.create(
            author=self.user,
            title="Sitemap Dynamic Post",
            excerpt="Sitemap test post",
            body_markdown="Sitemap content body",
            status=Post.Status.PUBLISHED,
        )
        page = self._create_page(title="Sitemap Dynamic Page", status=Page.Status.PUBLISHED)

        index_response = self.client.get(reverse("sitemap-index"))
        self.assertEqual(index_response.status_code, 200)
        self.assertContains(index_response, "xml-stylesheet")
        self.assertContains(index_response, "sitemap-posts.xml")
        self.assertContains(index_response, "sitemap-pages.xml")
        self.assertContains(index_response, "sitemap-static.xml")
        self.assertContains(index_response, "sitemap-policies.xml")

        sections_index_response = self.client.get(reverse("sitemap-sections-index"))
        self.assertEqual(sections_index_response.status_code, 200)
        self.assertContains(sections_index_response, "xml-stylesheet")
        self.assertContains(sections_index_response, "sitemap-policies.xml")

        unified_response = self.client.get(reverse("sitemap-unified"))
        self.assertEqual(unified_response.status_code, 200)
        self.assertContains(unified_response, "xml-stylesheet")
        self.assertContains(unified_response, post.get_absolute_url())
        self.assertContains(unified_response, page.get_absolute_url())
        self.assertContains(
            unified_response,
            reverse("pages:policy_detail", kwargs={"slug": "privacy-policy"}),
        )

        section_response = self.client.get(
            reverse("sitemap-section", kwargs={"section": "policies"})
        )
        self.assertEqual(section_response.status_code, 200)
        self.assertContains(section_response, "xml-stylesheet")
        self.assertContains(
            section_response,
            reverse("pages:policy_detail", kwargs={"slug": "privacy-policy"}),
        )

        xsl_response = self.client.get(reverse("sitemap-xsl"))
        self.assertEqual(xsl_response.status_code, 200)
        self.assertContains(xsl_response, "<xsl:stylesheet")

        robots_response = self.client.get(reverse("robots-txt"))
        self.assertEqual(robots_response.status_code, 200)
        self.assertContains(robots_response, "Sitemap:")

    def test_sitemap_routes_respect_feature_toggle(self):
        controls = FeatureControlSettings.get_solo()
        controls.enable_sitemap = False
        controls.save(update_fields=["enable_sitemap", "updated_at"])

        self.assertEqual(self.client.get(reverse("sitemap-index")).status_code, 404)
        self.assertEqual(self.client.get(reverse("sitemap-sections-index")).status_code, 404)
        self.assertEqual(self.client.get(reverse("sitemap-unified")).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("sitemap-section", kwargs={"section": "posts"})).status_code,
            404,
        )

        robots_response = self.client.get(reverse("robots-txt"))
        self.assertEqual(robots_response.status_code, 200)
        self.assertNotContains(robots_response, "Sitemap:")
