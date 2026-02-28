from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django_htmx.http import HttpResponseClientRedirect

from blog.models import render_markdown_to_safe_html
from blog.ui_feedback import attach_ui_feedback
from core.integrations import emit_platform_webhook
from core.models import FeatureControlSettings
from seo.services import audit_content_batch, seo_context_for_instance, seo_context_for_route

from .forms import PageForm, PageMarkdownPreviewForm
from .models import Page
from .policies import POLICY_MAP, POLICY_PAGES, POLICY_SLUGS
from .services import get_related_pages_algorithmic

logger = logging.getLogger(__name__)

def _can_access_page(page, user):
    if user.is_authenticated and (user == page.author or user.is_staff):
        return True

    return (
        page.status == Page.Status.PUBLISHED
        and page.published_at is not None
        and page.published_at <= timezone.now()
    )


def _get_visible_page_or_404(slug, user):
    page = get_object_or_404(Page.objects.select_related("author"), slug=slug)
    if not _can_access_page(page, user):
        raise Http404("Page not available")
    return page


def _build_policy_entry(policy, override_page=None):
    if override_page:
        return {
            "slug": override_page.slug,
            "title": override_page.title,
            "summary": override_page.summary or policy["summary"],
            "body_html": override_page.body_html,
            "updated_at": override_page.updated_at.date(),
            "source": "page",
        }
    return {
        "slug": policy["slug"],
        "title": policy["title"],
        "summary": policy["summary"],
        "body_html": render_markdown_to_safe_html(policy["body_markdown"]),
        "updated_at": policy["updated_at"],
        "source": "default",
    }


@require_GET
def page_list(request):
    pages = Page.objects.visible_to(request.user).select_related("author")

    query = (request.GET.get("q") or "").strip()
    if query:
        pages = pages.search(query)

    template_key = (request.GET.get("template") or "").strip()
    allowed_templates = {choice for choice, _ in Page.TemplateKey.choices}
    if template_key in allowed_templates:
        pages = pages.filter(template_key=template_key)

    sort = (request.GET.get("sort") or "latest").strip()
    if sort == "nav":
        pages = pages.order_by("nav_order", "title")
    else:
        pages = pages.order_by("-published_at", "-updated_at")

    context = {
        "pages": pages[:60],
        "query": query,
        "active_template": template_key,
        "active_sort": sort,
        "template_choices": Page.TemplateKey.choices,
    }
    context.update(
        seo_context_for_route(
            request,
            route_type="listing",
            title="Pages",
            description="Browse published pages, policy docs, and structured content.",
        )
    )
    return render(request, "pages/page_list.html", context)


@require_GET
def policy_index(request):
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_policy_pages:
        raise Http404("Policy center is disabled.")

    overrides = {
        page.slug: page
        for page in Page.objects.visible_to(request.user)
        .filter(slug__in=POLICY_SLUGS)
        .order_by("-updated_at")
    }
    policies = [
        _build_policy_entry(policy, overrides.get(policy["slug"])) for policy in POLICY_PAGES
    ]
    context = {"policies": policies}
    context.update(
        seo_context_for_route(
            request,
            route_type="policy",
            title="Policy Center",
            description="Privacy, terms, and policy pages for the site.",
        )
    )
    return render(request, "policies/policy_index.html", context)


@require_GET
def policy_detail(request, slug):
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_policy_pages:
        raise Http404("Policy pages are disabled.")

    policy = POLICY_MAP.get(slug)
    if not policy:
        raise Http404("Policy not available")

    override_page = (
        Page.objects.visible_to(request.user)
        .filter(slug=slug)
        .order_by("-updated_at")
        .first()
    )
    policy_entry = _build_policy_entry(policy, override_page)
    context = {"policy": policy_entry}
    context.update(
        seo_context_for_route(
            request,
            route_type="policy",
            title=policy_entry["title"],
            description=policy_entry["summary"],
            body_markdown=policy["body_markdown"],
            canonical_url=request.build_absolute_uri(
                reverse("pages:policy_detail", kwargs={"slug": slug})
            ),
        )
    )
    return render(request, "policies/policy_detail.html", context)


@require_GET
def page_detail(request, slug):
    page = _get_visible_page_or_404(slug, request.user)
    related_pages = get_related_pages_algorithmic(
        request.user,
        anchor_page=page,
        limit=4,
    )
    context = {
        "page": page,
        "related_pages": related_pages,
    }
    context.update(seo_context_for_instance(page, request=request))
    return render(request, "pages/page_detail.html", context)


@login_required
def page_manage(request):
    sort_by = (request.GET.get("sort") or "-updated_at").strip()
    valid_sorts = {"-updated_at", "-created_at", "-published_at", "title"}
    if sort_by not in valid_sorts:
        sort_by = "-updated_at"

    pages = (
        Page.objects.filter(author=request.user)
        .select_related("author")
        .order_by(sort_by, "-created_at")
    )
    context = {
        "pages": pages,
        "protected_policy_slugs": POLICY_SLUGS,
        "sort_by": sort_by,
    }
    return render(request, "pages/page_manage.html", context)


@login_required
@require_POST
def page_bulk_action(request):
    action = (request.POST.get("bulk_action") or "").strip()
    selected_ids = request.POST.getlist("selected_pages")

    feedback_level = "info"
    feedback_message = "No changes applied."

    if not selected_ids:
        messages.warning(request, "Select at least one page.")
        feedback_level = "warning"
        feedback_message = "Select at least one page."
        if request.htmx:
            response = HttpResponseClientRedirect(reverse("pages:manage"))
            return attach_ui_feedback(
                response,
                toast={"level": feedback_level, "message": feedback_message},
                inline={
                    "target": "pages-manage",
                    "level": feedback_level,
                    "message": feedback_message,
                },
            )
        return redirect("pages:manage")

    queryset = Page.objects.filter(author=request.user, id__in=selected_ids)
    if not queryset.exists():
        messages.warning(request, "No matching pages found.")
        feedback_level = "warning"
        feedback_message = "No matching pages found."
        if request.htmx:
            response = HttpResponseClientRedirect(reverse("pages:manage"))
            return attach_ui_feedback(
                response,
                toast={"level": feedback_level, "message": feedback_message},
                inline={
                    "target": "pages-manage",
                    "level": feedback_level,
                    "message": feedback_message,
                },
            )
        return redirect("pages:manage")

    now = timezone.now()
    count = queryset.count()

    needs_seo_refresh = False
    if action == "publish":
        queryset.update(status=Page.Status.PUBLISHED, published_at=now, updated_at=now)
        messages.success(request, f"{count} pages published.")
        feedback_level = "success"
        feedback_message = f"{count} pages published."
        needs_seo_refresh = True
    elif action == "review":
        queryset.update(status=Page.Status.REVIEW, updated_at=now)
        messages.success(request, f"{count} pages moved to review.")
        feedback_level = "success"
        feedback_message = f"{count} pages moved to review."
        needs_seo_refresh = True
    elif action == "archive":
        queryset.update(status=Page.Status.ARCHIVED, updated_at=now)
        messages.success(request, f"{count} pages archived.")
        feedback_level = "success"
        feedback_message = f"{count} pages archived."
        needs_seo_refresh = True
    elif action == "nav_on":
        queryset.update(show_in_navigation=True, updated_at=now)
        messages.success(request, f"{count} pages added to navigation.")
        feedback_level = "success"
        feedback_message = f"{count} pages added to navigation."
        needs_seo_refresh = True
    elif action == "nav_off":
        queryset.update(show_in_navigation=False, updated_at=now)
        messages.success(request, f"{count} pages removed from navigation.")
        feedback_level = "success"
        feedback_message = f"{count} pages removed from navigation."
        needs_seo_refresh = True
    elif action == "feature_on":
        queryset.update(is_featured=True, updated_at=now)
        messages.success(request, f"{count} pages marked as featured.")
        feedback_level = "success"
        feedback_message = f"{count} pages marked as featured."
        needs_seo_refresh = True
    elif action == "feature_off":
        queryset.update(is_featured=False, updated_at=now)
        messages.success(request, f"{count} pages removed from featured.")
        feedback_level = "success"
        feedback_message = f"{count} pages removed from featured."
        needs_seo_refresh = True
    elif action == "template_default":
        queryset.update(template_key=Page.TemplateKey.DEFAULT, updated_at=now)
        messages.success(request, f"{count} pages set to Default template.")
        feedback_level = "success"
        feedback_message = f"{count} pages set to Default template."
        needs_seo_refresh = True
    elif action == "template_landing":
        queryset.update(template_key=Page.TemplateKey.LANDING, updated_at=now)
        messages.success(request, f"{count} pages set to Landing template.")
        feedback_level = "success"
        feedback_message = f"{count} pages set to Landing template."
        needs_seo_refresh = True
    elif action == "template_docs":
        queryset.update(template_key=Page.TemplateKey.DOCUMENTATION, updated_at=now)
        messages.success(request, f"{count} pages set to Documentation template.")
        feedback_level = "success"
        feedback_message = f"{count} pages set to Documentation template."
        needs_seo_refresh = True
    elif action == "delete":
        protected = queryset.filter(slug__in=POLICY_SLUGS)
        deletable = queryset.exclude(slug__in=POLICY_SLUGS)
        deleted_count = deletable.count()
        if deleted_count:
            deletable.delete()
            messages.success(request, f"{deleted_count} pages deleted.")
            feedback_level = "success"
            feedback_message = f"{deleted_count} pages deleted."
        if protected.exists():
            messages.warning(request, "Policy pages are protected and were not deleted.")
            if deleted_count:
                feedback_level = "warning"
                feedback_message = (
                    f"{deleted_count} pages deleted. Policy pages were protected."
                )
            else:
                feedback_level = "warning"
                feedback_message = "Policy pages are protected and were not deleted."
    else:
        messages.error(request, "Unknown bulk action.")
        feedback_level = "error"
        feedback_message = "Unknown bulk action."

    if needs_seo_refresh:
        try:
            audit_content_batch("page", selected_ids, trigger="save", run_autopilot=True)
        except Exception:
            logger.exception("SEO refresh failed after page bulk action '%s'.", action)

    if request.htmx:
        response = HttpResponseClientRedirect(reverse("pages:manage"))
        return attach_ui_feedback(
            response,
            toast={"level": feedback_level, "message": feedback_message},
            inline={
                "target": "pages-manage",
                "level": feedback_level,
                "message": feedback_message,
            },
        )
    return redirect("pages:manage")


@login_required
def page_create(request):
    if request.method == "POST":
        form = PageForm(request.POST)
        if form.is_valid():
            page = form.save(commit=False)
            page.author = request.user
            page.save()
            form.save_m2m()
            page.record_revision(editor=request.user, note="Initial save")
            emit_platform_webhook(
                "page.created",
                {
                    "page_id": page.id,
                    "slug": page.slug,
                    "author_id": request.user.id,
                    "status": page.status,
                },
            )

            messages.success(request, "Page created successfully.")
            if request.htmx:
                response = HttpResponseClientRedirect(page.get_absolute_url())
                return attach_ui_feedback(
                    response,
                    toast={"level": "success", "message": "Page created successfully."},
                    inline={
                        "target": "page-form",
                        "level": "success",
                        "message": "Page created successfully.",
                    },
                )
            return redirect(page)
    else:
        form = PageForm()

    context = {
        "form": form,
        "mode": "Create",
        "preview_html": "",
    }
    return render(request, "pages/page_form.html", context)


@login_required
def page_update(request, slug):
    page = get_object_or_404(Page, slug=slug)
    if not (request.user == page.author or request.user.is_staff):
        raise Http404("Page not available")

    if request.method == "POST":
        form = PageForm(request.POST, instance=page)
        if form.is_valid():
            changed_fields = list(form.changed_data)
            page = form.save()
            emit_platform_webhook(
                "page.updated",
                {
                    "page_id": page.id,
                    "slug": page.slug,
                    "editor_id": request.user.id,
                    "changed_fields": changed_fields,
                },
            )
            if changed_fields:
                page.record_revision(
                    editor=request.user,
                    note=f"Updated fields: {', '.join(changed_fields)}",
                )

            messages.success(request, "Page updated successfully.")
            if request.htmx:
                response = HttpResponseClientRedirect(page.get_absolute_url())
                return attach_ui_feedback(
                    response,
                    toast={"level": "success", "message": "Page updated successfully."},
                    inline={
                        "target": "page-form",
                        "level": "success",
                        "message": "Page updated successfully.",
                    },
                )
            return redirect(page)
    else:
        form = PageForm(instance=page)

    context = {
        "form": form,
        "mode": "Update",
        "page": page,
        "preview_html": page.body_html,
    }
    return render(request, "pages/page_form.html", context)


@login_required
def page_delete(request, slug):
    page = get_object_or_404(Page, slug=slug)
    if not (request.user == page.author or request.user.is_staff):
        raise Http404("Page not available")
    if page.slug in POLICY_SLUGS:
        messages.error(request, "Policy pages are protected and cannot be deleted.")
        return redirect("pages:manage")

    if request.method == "POST":
        emit_platform_webhook(
            "page.deleted",
            {
                "page_id": page.id,
                "slug": page.slug,
                "editor_id": request.user.id,
            },
        )
        page.delete()
        messages.success(request, "Page deleted.")
        return redirect("pages:manage")

    return render(request, "pages/page_confirm_delete.html", {"page": page})


@login_required
def page_revisions(request, slug):
    page = get_object_or_404(Page, slug=slug)
    if not (request.user == page.author or request.user.is_staff):
        raise Http404("Page not available")

    revisions = page.revisions.select_related("editor").all()
    return render(
        request,
        "pages/page_revisions.html",
        {
            "page": page,
            "revisions": revisions,
        },
    )


@login_required
@require_POST
def markdown_preview(request):
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_quick_preview:
        return HttpResponseBadRequest("Markdown preview is disabled.")

    form = PageMarkdownPreviewForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid markdown preview request")

    preview_html = render_markdown_to_safe_html(form.cleaned_data.get("body_markdown", ""))
    return render(
        request,
        "pages/partials/editor_preview.html",
        {
            "preview_html": preview_html,
        },
    )


@require_GET
def api_pages(request):
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_public_api:
        return JsonResponse({"detail": "Public API is disabled."}, status=403)

    pages = Page.objects.visible_to(request.user).select_related("author")

    query = (request.GET.get("q") or "").strip()
    if query:
        pages = pages.search(query)

    try:
        page_number = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page_number = 1

    try:
        per_page = max(min(int(request.GET.get("per_page", "12")), 50), 1)
    except ValueError:
        per_page = 12

    total = pages.count()
    start = (page_number - 1) * per_page
    end = start + per_page

    records = list(pages.order_by("-published_at", "-updated_at")[start:end])

    return JsonResponse(
        {
            "meta": {
                "page": page_number,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
                "generated_at": timezone.now().isoformat(),
            },
            "data": [
                {
                    "id": page.id,
                    "title": page.title,
                    "slug": page.slug,
                    "summary": page.summary,
                    "url": page.get_absolute_url(),
                    "status": page.status,
                    "template_key": page.template_key,
                    "show_in_navigation": page.show_in_navigation,
                    "nav_order": page.nav_order,
                    "author": page.author.username,
                    "published_at": page.published_at.isoformat() if page.published_at else None,
                    "updated_at": page.updated_at.isoformat(),
                    "reading_time": page.reading_time,
                }
                for page in records
            ],
        }
    )


