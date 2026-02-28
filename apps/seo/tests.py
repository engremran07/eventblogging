from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from blog.models import Post
from core.models import SeoSettings
from pages.models import Page

from .interlink import suggest_internal_links
from .models import SeoAuditSnapshot, SeoEngineSettings, SeoIssue, SeoRedirectRule, SeoSuggestion
from .models import SeoScanJob, SeoSuggestionRevision, TaxonomySynonymGroup, TaxonomySynonymTerm
from .services import audit_instance, run_autopilot_for_instance


class SeoPipelineTests(TestCase):
    def setUp(self):
        self.author = get_user_model().objects.create_user(
            username="seo_writer",
            password="strong-password",
        )
        self.staff = get_user_model().objects.create_user(
            username="seo_staff",
            password="strong-password",
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="seo_superuser",
            email="seo_superuser@example.com",
            password="strong-password",
        )

    def _create_post(self, title, body, *, status=Post.Status.PUBLISHED):
        return Post.objects.create(
            author=self.author,
            title=title,
            excerpt=body[:140],
            body_markdown=body,
            status=status,
        )

    def _create_page(self, title, body, *, status=Page.Status.PUBLISHED):
        return Page.objects.create(
            author=self.author,
            title=title,
            summary=body[:140],
            body_markdown=body,
            status=status,
        )

    def test_audit_instance_creates_snapshot_and_issue_rows(self):
        self._create_page(
            "Django deployment guide",
            "Deployment checklist for production Django apps.",
        )
        post = self._create_post(
            "Algorithmic SEO with Django",
            "This post explains algorithmic seo checks and internal linking strategy for django blogs.",
        )

        snapshot = audit_instance(post, trigger="manual")
        self.assertIsNotNone(snapshot)
        self.assertTrue(SeoAuditSnapshot.objects.filter(pk=snapshot.id).exists())
        self.assertTrue(SeoIssue.objects.filter(snapshot=snapshot).exists())

    def test_search_semantic_endpoint_returns_scores_and_passages(self):
        self._create_post(
            "Django deployment checklist",
            "Django deployment requires migrations, cache checks, and security review.",
        )
        self._create_page(
            "Deployment policy page",
            "This page documents deployment policy and release quality gates.",
        )

        response = self.client.get(
            reverse("seo:search_semantic"),
            {"q": "django deployment"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)
        self.assertGreaterEqual(len(payload["results"]), 1)
        first = payload["results"][0]
        self.assertIn("scores", first)
        self.assertIn("semantic", first["scores"])
        self.assertIn("matched_passages", first)

    def test_related_semantic_endpoint_returns_explanations(self):
        anchor = self._create_post(
            "Django SEO architecture",
            "Django SEO architecture with canonical metadata and internal links.",
        )
        self._create_post(
            "Django canonical metadata",
            "Canonical metadata for django posts and structured data implementation.",
        )
        self._create_post(
            "Python testing workflow",
            "Tests and QA workflow for content pipelines.",
        )

        response = self.client.get(
            reverse("seo:related_semantic", kwargs={"post_id": anchor.id}),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)
        self.assertGreaterEqual(len(payload["results"]), 1)
        first = payload["results"][0]
        self.assertIn("components", first)
        self.assertIn("recommendation_type", first)

    def test_internal_link_suggestions_handle_page_summary_model_fields(self):
        self._create_page(
            "Canonical Playbook",
            "Canonical metadata guidance for indexing and internal links.",
        )
        source = self._create_post(
            "Internal linking primer",
            (
                "Canonical metadata guidance improves discoverability. "
                "Internal links should connect related resources."
            ),
        )

        suggestions = suggest_internal_links(source, max_suggestions=6)
        self.assertIsInstance(suggestions, list)
        for row in suggestions:
            self.assertIn("anchor_text", row)
            self.assertIn("target_url", row)
            self.assertIn("target_type", row)

    def test_reindex_endpoint_requires_staff(self):
        post = self._create_post("Reindex target", "Body for reindex target.")

        self.client.login(username="seo_writer", password="strong-password")
        forbidden = self.client.post(reverse("seo:reindex_post", kwargs={"post_id": post.id}))
        self.assertIn(forbidden.status_code, {302, 403})

        self.client.login(username="seo_staff", password="strong-password")
        allowed = self.client.post(reverse("seo:reindex_post", kwargs={"post_id": post.id}))
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()["ok"])

    def test_live_check_inline_returns_htmx_fragment(self):
        self.client.login(username="seo_writer", password="strong-password")
        response = self.client.post(
            reverse("seo:live_check_inline", kwargs={"content_type": "post"}),
            {
                "title": "Realtime SEO check",
                "slug": "realtime-seo-check",
                "excerpt": "Inline validation for metadata and body quality.",
                "meta_title": "Realtime SEO check",
                "meta_description": "Inline validation for metadata and body quality.",
                "canonical_url": "https://example.com/realtime-seo-check",
                "body_markdown": "Inline SEO checks should report title, links, schema, and canonical quality.",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Realtime SEO Check")

    def test_live_check_inline_respects_live_checks_toggle(self):
        settings = SeoEngineSettings.get_solo()
        settings.enable_live_checks = False
        settings.save(update_fields=["enable_live_checks", "updated_at"])

        self.client.login(username="seo_writer", password="strong-password")
        response = self.client.post(
            reverse("seo:live_check_inline", kwargs={"content_type": "post"}),
            {"title": "Disabled checks", "body_markdown": "Body"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "disabled", status_code=403)

    def test_run_autopilot_for_instance_approves_safe_suggestions(self):
        post = self._create_post("Autopilot Instance", "Autopilot instance body")
        ct = ContentType.objects.get_for_model(Post)
        suggestion = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={
                "meta_title": "Autopilot Instance Meta",
                "meta_description": "Autopilot instance description.",
                "canonical_url": "https://example.com/autopilot-instance",
            },
            confidence=0.95,
            status=SeoSuggestion.Status.PENDING,
        )
        result = run_autopilot_for_instance(post, min_confidence=0.9)
        self.assertTrue(result["ok"])
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, SeoSuggestion.Status.APPLIED)

    def test_action_center_requires_staff(self):
        self.client.login(username="seo_writer", password="strong-password")
        blocked = self.client.get(reverse("admin_config:seo_action_center"))
        self.assertIn(blocked.status_code, {302, 403})

        self.client.login(username="seo_staff", password="strong-password")
        allowed = self.client.get(reverse("admin_config:seo_action_center"), follow=True)
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, "SEO Control")

    def test_review_endpoints_approve_and_reject(self):
        post = self._create_post("Review candidate", "SEO candidate body text.")
        ct = ContentType.objects.get_for_model(Post)
        approve_candidate = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={
                "meta_title": "Approved Meta Title",
                "meta_description": "Approved description from queue.",
                "canonical_url": "https://example.com/post/review-candidate",
            },
            confidence=0.9,
        )
        reject_candidate = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={"meta_title": "Reject Me"},
            confidence=0.2,
        )

        self.client.login(username="seo_staff", password="strong-password")

        approve_response = self.client.post(
            reverse("seo:review_approve", kwargs={"candidate_id": approve_candidate.id})
        )
        self.assertEqual(approve_response.status_code, 200)
        approve_candidate.refresh_from_db()
        self.assertEqual(approve_candidate.status, SeoSuggestion.Status.APPLIED)

        reject_response = self.client.post(
            reverse("seo:review_reject", kwargs={"candidate_id": reject_candidate.id})
        )
        self.assertEqual(reject_response.status_code, 200)
        reject_candidate.refresh_from_db()
        self.assertEqual(reject_candidate.status, SeoSuggestion.Status.REJECTED)

    def test_legacy_action_center_routes_redirect_to_seo_control(self):
        post = self._create_post("Action Center Candidate", "Candidate content for queue.")
        ct = ContentType.objects.get_for_model(Post)
        single = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={"meta_title": "Single Apply"},
            confidence=0.8,
        )
        bulk_one = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={"meta_title": "Bulk One"},
            confidence=0.7,
        )
        bulk_two = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={"meta_title": "Bulk Two"},
            confidence=0.7,
        )

        self.client.login(username="seo_staff", password="strong-password")
        single_response = self.client.post(
            reverse(
                "admin_config:seo_action_center_single",
                kwargs={"suggestion_id": single.id, "action": "approve"},
            ),
            HTTP_HX_REQUEST="true",
        )
        self.assertIn(single_response.status_code, {302, 301})
        self.assertIn(reverse("admin_config:seo_control"), single_response.url)
        single.refresh_from_db()
        self.assertEqual(single.status, SeoSuggestion.Status.PENDING)

        bulk_response = self.client.post(
            reverse("admin_config:seo_action_center_bulk"),
            {
                "bulk_action": "reject",
                "selected_suggestions": [str(bulk_one.id), str(bulk_two.id)],
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertIn(bulk_response.status_code, {302, 301})
        self.assertIn(reverse("admin_config:seo_control"), bulk_response.url)
        bulk_one.refresh_from_db()
        bulk_two.refresh_from_db()
        self.assertEqual(bulk_one.status, SeoSuggestion.Status.PENDING)
        self.assertEqual(bulk_two.status, SeoSuggestion.Status.PENDING)

    def test_control_suggestion_single_and_bulk_actions(self):
        post = self._create_post("Control Candidate", "Candidate content for queue.")
        ct = ContentType.objects.get_for_model(Post)
        single = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={"meta_title": "Single Apply"},
            confidence=0.8,
        )
        bulk_one = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={"meta_title": "Bulk One"},
            confidence=0.7,
        )
        bulk_two = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={"meta_title": "Bulk Two"},
            confidence=0.7,
        )

        self.client.login(username="seo_staff", password="strong-password")
        single_response = self.client.post(
            reverse(
                "admin_config:seo_control_suggestion_action",
                kwargs={"suggestion_id": single.id, "action": "approve"},
            ),
            follow=True,
        )
        self.assertEqual(single_response.status_code, 200)
        single.refresh_from_db()
        self.assertEqual(single.status, SeoSuggestion.Status.APPLIED)

        self.client.login(username="seo_superuser", password="strong-password")
        bulk_response = self.client.post(
            reverse("admin_config:seo_control_suggestion_bulk"),
            {
                "bulk_action": "reject",
                "selected_suggestions": [str(bulk_one.id), str(bulk_two.id)],
            },
            follow=True,
        )
        self.assertEqual(bulk_response.status_code, 200)
        bulk_one.refresh_from_db()
        bulk_two.refresh_from_db()
        self.assertEqual(bulk_one.status, SeoSuggestion.Status.REJECTED)
        self.assertEqual(bulk_two.status, SeoSuggestion.Status.REJECTED)

    def test_delete_creates_redirect_artifacts(self):
        post = self._create_post("Delete Redirect Target", "Redirect body text")
        old_path = post.get_absolute_url()
        post.delete()

        self.assertTrue(
            SeoSuggestion.objects.filter(
                suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
                payload_json__old_path=old_path,
            ).exists()
        )
        self.assertTrue(
            SeoRedirectRule.objects.filter(
                old_path=old_path,
                status_code=SeoRedirectRule.StatusCode.GONE,
            ).exists()
        )

    def test_recreated_post_path_disables_stale_gone_redirect(self):
        post = self._create_post("Recreated Path Target", "Redirect body text")
        old_path = post.get_absolute_url()
        post.delete()
        recreated = self._create_post("Recreated Path Target", "Replacement body text")
        self.assertEqual(recreated.get_absolute_url(), old_path)

        response = self.client.get(old_path)
        self.assertEqual(response.status_code, 200)

        rule = SeoRedirectRule.objects.get(old_path=old_path)
        self.assertFalse(rule.is_active)

    def test_recreated_page_path_disables_stale_gone_redirect(self):
        page = self._create_page("Recreated Page Path", "Redirect body text")
        old_path = page.get_absolute_url()
        page.delete()
        recreated = self._create_page("Recreated Page Path", "Replacement body text")
        self.assertEqual(recreated.get_absolute_url(), old_path)

        response = self.client.get(old_path)
        self.assertEqual(response.status_code, 200)

        rule = SeoRedirectRule.objects.get(old_path=old_path)
        self.assertFalse(rule.is_active)

    def test_seo_control_requires_staff(self):
        self.client.login(username="seo_writer", password="strong-password")
        blocked = self.client.get(reverse("admin_config:seo_control"))
        self.assertIn(blocked.status_code, {302, 403})

        self.client.login(username="seo_staff", password="strong-password")
        allowed = self.client.get(reverse("admin_config:seo_control"))
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, "SEO Control")

    def test_seo_overview_renders_as_distinct_page(self):
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.get(reverse("admin_config:seo_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SEO Overview")
        self.assertContains(response, "Open Audit Queue")

    def test_seo_queue_renders_without_redirect_and_defaults_to_onsite(self):
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.get(reverse("admin_config:seo_queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SEO Audit Queue")
        self.assertContains(response, 'data-control-section="onsite"')
        self.assertContains(response, 'data-control-section="redirects"')

    def test_seo_queue_preserves_page_query_for_initial_onsite_load(self):
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.get(reverse("admin_config:seo_queue"), {"onsite_page": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "onsite_page=2")

    def test_onsite_section_excludes_suggestions_for_content_without_open_issue(self):
        with_issue = self._create_post("Issue-backed target", "Body with issue-backed suggestion.")
        clean_post = self._create_post("Clean target", "Body for clean suggestion.")
        ct = ContentType.objects.get_for_model(Post)
        issue_backed = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=with_issue.id,
            suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
            payload_json={
                "old_path": "/issue-backed-target/",
                "suggested_target": with_issue.get_absolute_url(),
                "status_code": 301,
            },
            confidence=0.9,
            status=SeoSuggestion.Status.PENDING,
        )
        clean_suggestion = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=clean_post.id,
            suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
            payload_json={
                "old_path": "/clean-target/",
                "suggested_target": clean_post.get_absolute_url(),
                "status_code": 301,
            },
            confidence=0.9,
            status=SeoSuggestion.Status.PENDING,
        )
        snapshot = SeoAuditSnapshot.objects.create(
            content_type=ct,
            object_id=with_issue.id,
            url=with_issue.get_absolute_url(),
            route_type=SeoAuditSnapshot.RouteType.POST,
            score=52.0,
        )
        SeoIssue.objects.create(
            snapshot=snapshot,
            check_key="missing_meta_description",
            severity=SeoIssue.Severity.WARNING,
            status=SeoIssue.Status.OPEN,
            message="Meta description missing.",
        )

        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.get(
            reverse("admin_config:seo_control_section", kwargs={"section": "onsite"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"S-{issue_backed.id}")
        self.assertNotContains(response, f"S-{clean_suggestion.id}")
        self.assertNotContains(response, clean_post.title)

    def test_onsite_section_supports_task_pagination(self):
        post = self._create_post("Paged queue target", "Body for paged queue target.")
        ct = ContentType.objects.get_for_model(Post)
        snapshot = SeoAuditSnapshot.objects.create(
            content_type=ct,
            object_id=post.id,
            url=post.get_absolute_url(),
            route_type=SeoAuditSnapshot.RouteType.POST,
            score=47.0,
        )
        SeoIssue.objects.create(
            snapshot=snapshot,
            check_key="title_length_issue",
            severity=SeoIssue.Severity.WARNING,
            status=SeoIssue.Status.OPEN,
            message="Title is outside ideal range.",
        )
        for index in range(26):
            SeoSuggestion.objects.create(
                content_type=ct,
                object_id=post.id,
                suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
                payload_json={
                    "old_path": f"/paged-queue-{index}/",
                    "suggested_target": post.get_absolute_url(),
                    "status_code": 301,
                },
                confidence=0.9,
                status=SeoSuggestion.Status.PENDING,
            )

        self.client.login(username="seo_staff", password="strong-password")
        first_page = self.client.get(
            reverse("admin_config:seo_control_section", kwargs={"section": "onsite"}),
            {"onsite_page": "1"},
        )
        self.assertEqual(first_page.status_code, 200)
        self.assertContains(first_page, "Page 1 of 2")

        second_page = self.client.get(
            reverse("admin_config:seo_control_section", kwargs={"section": "onsite"}),
            {"onsite_page": "2"},
        )
        self.assertEqual(second_page.status_code, 200)
        self.assertContains(second_page, "Page 2 of 2")

    def test_redirects_section_shows_dedicated_redirect_workspace(self):
        post = self._create_post("Redirect workspace target", "Body text for redirects workspace.")
        ct = ContentType.objects.get_for_model(Post)
        suggestion = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
            payload_json={
                "old_path": "/redirect-workspace-target/",
                "suggested_target": post.get_absolute_url(),
                "status_code": 301,
            },
            confidence=0.9,
            status=SeoSuggestion.Status.PENDING,
        )
        snapshot = SeoAuditSnapshot.objects.create(
            content_type=ct,
            object_id=post.id,
            url=post.get_absolute_url(),
            route_type=SeoAuditSnapshot.RouteType.POST,
            score=49.0,
        )
        SeoIssue.objects.create(
            snapshot=snapshot,
            check_key="missing_meta_description",
            severity=SeoIssue.Severity.WARNING,
            status=SeoIssue.Status.OPEN,
            message="Broken internal link discovered.",
        )

        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.get(
            reverse("admin_config:seo_control_section", kwargs={"section": "redirects"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Redirect Queue Board")
        self.assertContains(response, f"S-{suggestion.id}")

    def test_scan_job_start_and_progress_endpoint(self):
        self.client.login(username="seo_staff", password="strong-password")
        start_response = self.client.post(
            reverse("admin_config:seo_control_run"),
            {"job_type": "posts", "notes": "test run"},
            follow=True,
        )
        self.assertEqual(start_response.status_code, 200)
        job = SeoScanJob.objects.order_by("-id").first()
        self.assertIsNotNone(job)
        progress = self.client.get(
            reverse("admin_config:seo_control_job_progress", kwargs={"job_id": job.id})
        )
        self.assertEqual(progress.status_code, 200)
        payload = progress.json()
        self.assertEqual(payload["job_id"], job.id)
        self.assertIn("progress_percent", payload)

    def test_internal_linking_scan_has_separate_job_type_and_history(self):
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.post(
            reverse("admin_config:seo_interlink_scan_start"),
            {"notes": "interlink-only run"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        job = SeoScanJob.objects.order_by("-id").first()
        self.assertIsNotNone(job)
        self.assertEqual(job.job_type, SeoScanJob.JobType.INTERLINKS)
        self.assertContains(response, "/admin/seo/control/interlinking/")

    def test_onsite_section_shows_descriptive_pending_task_backlog(self):
        post = self._create_post("Task backlog target", "Body text for backlog.")
        ct = ContentType.objects.get_for_model(Post)
        SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
            payload_json={
                "old_path": "/old-task-backlog-target/",
                "suggested_target": post.get_absolute_url(),
                "status_code": 301,
            },
            confidence=0.91,
            status=SeoSuggestion.Status.PENDING,
        )
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.get(
            reverse("admin_config:seo_control_section", kwargs={"section": "onsite"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "On-site SEO Backlog")
        self.assertContains(response, "Recommended Fix")

    def test_metadata_section_shows_template_injection_workspace(self):
        post = self._create_post("Metadata section target", "Body text for metadata section.")
        ct = ContentType.objects.get_for_model(Post)
        SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={
                "meta_title": "Metadata section target",
                "meta_description": "Metadata queue card in dedicated section.",
                "canonical_url": post.get_absolute_url(),
            },
            confidence=0.86,
            status=SeoSuggestion.Status.PENDING,
        )
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.get(
            reverse("admin_config:seo_control_section", kwargs={"section": "metadata"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Metadata Queue")
        self.assertContains(response, "Metadata Injection Status")

    def test_queue_edit_creates_revision_and_marks_needs_correction(self):
        post = self._create_post("Queue edit target", "Queue edit content.")
        ct = ContentType.objects.get_for_model(Post)
        suggestion = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={"meta_title": "Old"},
            confidence=0.5,
            status=SeoSuggestion.Status.PENDING,
        )
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.post(
            reverse("admin_config:seo_control_suggestion_edit", kwargs={"suggestion_id": suggestion.id}),
            {
                "payload_json": '{"meta_title": "New title"}',
                "note": "updated payload",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, SeoSuggestion.Status.NEEDS_CORRECTION)
        self.assertTrue(SeoSuggestionRevision.objects.filter(suggestion=suggestion).exists())

    def test_synonym_group_term_and_export(self):
        self.client.login(username="seo_staff", password="strong-password")
        create_response = self.client.post(
            reverse("admin_config:taxonomy_synonym_group_create"),
            {"name": "Cloud terms", "scope": "tags", "is_active": "on"},
            follow=True,
        )
        self.assertEqual(create_response.status_code, 200)
        group = TaxonomySynonymGroup.objects.get(name="Cloud terms")
        add_response = self.client.post(
            reverse("admin_config:taxonomy_synonym_term_add", kwargs={"group_id": group.id}),
            {"term": "saas", "is_canonical": "on", "weight": "1.5"},
            follow=True,
        )
        self.assertEqual(add_response.status_code, 200)
        self.assertTrue(TaxonomySynonymTerm.objects.filter(group=group, term="saas").exists())
        export_response = self.client.get(reverse("admin_config:taxonomy_synonym_export"))
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response["Content-Type"], "application/json")

    def test_seo_control_autopilot_approves_safe_suggestions(self):
        post = self._create_post("Autopilot target", "Autopilot body text")
        ct = ContentType.objects.get_for_model(Post)
        suggestion = SeoSuggestion.objects.create(
            content_type=ct,
            object_id=post.id,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
            payload_json={
                "meta_title": "Autopilot Meta",
                "meta_description": "Autopilot description",
                "canonical_url": "https://example.com/autopilot-target",
            },
            confidence=0.95,
            status=SeoSuggestion.Status.PENDING,
        )
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.post(
            reverse("admin_config:seo_control_autopilot"),
            {"min_confidence": "0.90", "limit": "20"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, SeoSuggestion.Status.APPLIED)

    def test_seo_control_settings_section_renders_global_seo_fields(self):
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.get(
            reverse("admin_config:seo_control_section", kwargs={"section": "settings"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="default_meta_title"')
        self.assertContains(response, 'name="google_site_verification"')
        self.assertContains(response, 'name="autopilot_min_confidence"')

    def test_seo_control_settings_save_updates_engine_and_global_defaults(self):
        self.client.login(username="seo_staff", password="strong-password")
        response = self.client.post(
            reverse("admin_config:seo_control_settings_save"),
            {
                "autopilot_min_confidence": "0.91",
                "link_suggestion_min_score": "0.61",
                "min_links_per_doc": "4",
                "whitehat_cap_max_links": "9",
                "canonical_query_allowlist": "utm_source,utm_medium",
                "enable_checks": "on",
                "enable_live_checks": "",
                "auto_fix_enabled": "on",
                "auto_update_published_links": "",
                "noindex_paginated_filters": "on",
                "apply_interlinks_on_audit": "on",
                "default_meta_title": "Unified SEO Platform",
                "default_meta_description": "Unified SEO defaults and verification controls.",
                "canonical_base_url": "https://example.com",
                "default_og_image_url": "https://example.com/og-default.png",
                "twitter_site_handle": "@unifiedseo",
                "organization_schema_name": "Unified SEO Labs",
                "organization_schema_url": "https://example.com/company",
                "google_site_verification": "google-token-123",
                "bing_site_verification": "bing-token-456",
                "yandex_site_verification": "yandex-token-789",
                "pinterest_site_verification": "pin-token-000",
                "robots_index": "on",
                "robots_follow": "",
                "enable_open_graph": "on",
                "enable_twitter_cards": "",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        engine = SeoEngineSettings.get_solo()
        defaults = SeoSettings.get_solo()

        self.assertAlmostEqual(engine.autopilot_min_confidence, 0.91, places=2)
        self.assertAlmostEqual(engine.link_suggestion_min_score, 0.61, places=2)
        self.assertEqual(engine.min_links_per_doc, 4)
        self.assertEqual(engine.whitehat_cap_max_links, 9)
        self.assertEqual(engine.canonical_query_allowlist, "utm_source,utm_medium")
        self.assertTrue(engine.enable_checks)
        self.assertFalse(engine.enable_live_checks)
        self.assertTrue(engine.auto_fix_enabled)
        self.assertFalse(engine.auto_update_published_links)
        self.assertTrue(engine.noindex_paginated_filters)
        self.assertTrue(engine.apply_interlinks_on_audit)

        self.assertEqual(defaults.default_meta_title, "Unified SEO Platform")
        self.assertEqual(
            defaults.default_meta_description,
            "Unified SEO defaults and verification controls.",
        )
        self.assertEqual(defaults.canonical_base_url, "https://example.com")
        self.assertEqual(defaults.default_og_image_url, "https://example.com/og-default.png")
        self.assertEqual(defaults.twitter_site_handle, "@unifiedseo")
        self.assertEqual(defaults.organization_schema_name, "Unified SEO Labs")
        self.assertEqual(defaults.organization_schema_url, "https://example.com/company")
        self.assertEqual(defaults.google_site_verification, "google-token-123")
        self.assertEqual(defaults.bing_site_verification, "bing-token-456")
        self.assertEqual(defaults.yandex_site_verification, "yandex-token-789")
        self.assertEqual(defaults.pinterest_site_verification, "pin-token-000")
        self.assertTrue(defaults.robots_index)
        self.assertFalse(defaults.robots_follow)
        self.assertTrue(defaults.enable_open_graph)
        self.assertFalse(defaults.enable_twitter_cards)
