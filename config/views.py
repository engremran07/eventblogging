from django.contrib.sitemaps.views import index as django_sitemap_index
from django.contrib.sitemaps.views import sitemap as django_sitemap
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from core.models import FeatureControlSettings

from .sitemaps import section_sitemaps, unified_sitemaps


@require_GET
def sitemap_xsl(request):
    content = render(request, "sitemap.xsl", {}).content
    response = HttpResponse(content, content_type="application/xslt+xml; charset=utf-8")
    response["X-Robots-Tag"] = "noindex"
    return response


@require_GET
def sitemap_unified(request):
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_sitemap:
        raise Http404("Sitemap is disabled.")
    return django_sitemap(
        request,
        sitemaps=unified_sitemaps,
        section="all",
        template_name="sitemap.xml",
    )


@require_GET
def sitemap_sections_index(request):
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_sitemap:
        raise Http404("Sitemap is disabled.")
    return django_sitemap_index(
        request,
        sitemaps=section_sitemaps,
        sitemap_url_name="sitemap-section",
        template_name="sitemap_index.xml",
    )


@require_GET
def sitemap_section(request, section):
    controls = FeatureControlSettings.get_solo()
    if not controls.enable_sitemap:
        raise Http404("Sitemap is disabled.")
    return django_sitemap(
        request,
        sitemaps=section_sitemaps,
        section=section,
        template_name="sitemap.xml",
    )


def handler404_view(request, exception=None):
    """Custom 404 page — search box helps visitors recover."""
    return render(request, "errors/404.html", {"page_title": "Page Not Found"}, status=404)


def handler500_view(request):
    """
    Custom 500 page.
    Deliberately avoids context processors (which may themselves be broken)
    by using a standalone template that does not extend base.html.
    """
    from django.template import loader

    html = loader.render_to_string("errors/500.html")
    from django.http import HttpResponseServerError

    return HttpResponseServerError(html)


@require_GET
def robots_txt(request):
    controls = FeatureControlSettings.get_solo()
    sitemap_enabled = bool(controls.enable_sitemap)
    sitemap_url = request.build_absolute_uri(reverse("sitemap-index")) if sitemap_enabled else ""
    sitemap_sections_url = (
        request.build_absolute_uri(reverse("sitemap-unified")) if sitemap_enabled else ""
    )
    content = render(
        request,
        "robots.txt",
        {
            "sitemap_url": sitemap_url,
            "sitemap_sections_url": sitemap_sections_url,
            "sitemap_enabled": sitemap_enabled,
        },
    ).content
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


@require_GET
def healthz(request):
    """Health check endpoint for Render / load balancers."""
    import logging

    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return HttpResponse("ok", content_type="text/plain", status=200)
    except Exception:
        logging.getLogger(__name__).warning("Health check failed: DB unreachable")
        return HttpResponse("db unavailable", content_type="text/plain", status=503)
