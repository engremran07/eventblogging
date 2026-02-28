from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin

from django.urls import reverse

from core.models import SeoSettings as SiteSeoSettings

from .models import SeoMetadataLock, SeoRouteProfile


@dataclass
class ResolvedMetadata:
    title: str
    description: str
    canonical: str
    robots: str
    alternates: dict
    open_graph: dict
    twitter: dict
    json_ld: list

    def to_dict(self):
        return asdict(self)


def _build_absolute_url(request, path: str):
    if request is None:
        return path
    return request.build_absolute_uri(path)


def _canonical_from_base(base_url: str, path: str):
    if not base_url:
        return path
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _resolve_route_profile(route_name: str):
    if not route_name:
        return None
    return SeoRouteProfile.objects.filter(route_name=route_name, enabled=True).first()


def _organization_schema(site_settings):
    if not site_settings.organization_schema_name:
        return None
    org_url = site_settings.organization_schema_url or ""
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": site_settings.organization_schema_name,
        "url": org_url,
    }


def _content_schema(adapter, canonical):
    if adapter.route_type == "post":
        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": adapter.meta_title or adapter.title,
            "description": adapter.meta_description,
            "datePublished": adapter.published_at.isoformat() if adapter.published_at else None,
            "dateModified": adapter.updated_at.isoformat() if adapter.updated_at else None,
            "url": canonical,
        }
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": adapter.meta_title or adapter.title,
        "description": adapter.meta_description,
        "dateModified": adapter.updated_at.isoformat() if adapter.updated_at else None,
        "url": canonical,
    }


def _build_robots(site_seo, *, noindex=False):
    index_part = "noindex" if noindex else ("index" if site_seo.robots_index else "noindex")
    follow_part = "follow" if site_seo.robots_follow else "nofollow"
    return f"{index_part},{follow_part},max-snippet:-1,max-image-preview:large"


def resolve_metadata(adapter, *, request=None):
    site_seo = SiteSeoSettings.get_solo()
    route_name = ""
    if request and request.resolver_match:
        route_name = request.resolver_match.view_name or ""
    route_profile = _resolve_route_profile(route_name)

    path = adapter.get_absolute_url() if hasattr(adapter, "get_absolute_url") else "/"
    canonical_raw = (adapter.canonical_url or "").strip()
    if canonical_raw:
        canonical = canonical_raw
    else:
        canonical = _canonical_from_base(site_seo.canonical_base_url, path)
        canonical = _build_absolute_url(request, canonical) if request else canonical

    title = (adapter.meta_title or adapter.title or "").strip()
    if route_profile and route_profile.title_template:
        title = route_profile.title_template.format(title=title, site=site_seo.default_meta_title or "")
    title = title or site_seo.default_meta_title or adapter.title or "Untitled"
    title = title[:70]

    description = (adapter.meta_description or "").strip()
    if not description:
        description = site_seo.default_meta_description or ""
    if not description:
        description = (adapter.summary or adapter.excerpt or adapter.body_markdown or "")[:170]
    description = description[:170]

    noindex = False
    if request:
        has_page = request.GET.get("page")
        page_number = 1
        if has_page:
            try:
                page_number = int(has_page)
            except (TypeError, ValueError):
                page_number = 1
        if page_number > 1:
            from .models import SeoEngineSettings

            engine_settings = SeoEngineSettings.get_solo()
            if engine_settings.noindex_paginated_filters:
                noindex = True
    robots = _build_robots(site_seo, noindex=noindex)

    image_url = adapter.og_image_url or site_seo.default_og_image_url
    if image_url and request and image_url.startswith("/"):
        image_url = request.build_absolute_uri(image_url)

    og_type = "article" if adapter.route_type == "post" else "website"
    if route_profile and route_profile.og_type:
        og_type = route_profile.og_type

    open_graph = {
        "type": og_type,
        "title": title,
        "description": description,
        "url": canonical,
        "image": image_url or "",
        "published_time": adapter.published_at.isoformat() if adapter.published_at else "",
        "modified_time": adapter.updated_at.isoformat() if adapter.updated_at else "",
    }
    twitter = {
        "card": "summary_large_image" if image_url else "summary",
        "title": title,
        "description": description,
        "image": image_url or "",
        "site": site_seo.twitter_site_handle or "",
    }

    json_ld = []
    org_schema = _organization_schema(site_seo)
    if org_schema:
        json_ld.append(org_schema)
    json_ld.append(_content_schema(adapter, canonical))

    # Honor manual locks where available.
    try:
        lock = SeoMetadataLock.objects.get(
            content_type=adapter.content_type,
            object_id=adapter.pk,
        )
        if lock.lock_title and adapter.meta_title:
            title = adapter.meta_title[:70]
            open_graph["title"] = title
            twitter["title"] = title
        if lock.lock_description and adapter.meta_description:
            description = adapter.meta_description[:170]
            open_graph["description"] = description
            twitter["description"] = description
        if lock.lock_canonical and adapter.canonical_url:
            canonical = adapter.canonical_url
            open_graph["url"] = canonical
        if lock.lock_og and adapter.og_image_url:
            open_graph["image"] = adapter.og_image_url
        if lock.lock_twitter and adapter.og_image_url:
            twitter["image"] = adapter.og_image_url
    except SeoMetadataLock.DoesNotExist:
        pass

    alternates = {"canonical": canonical}
    try:
        alternates["sitemap"] = reverse("sitemap-index")
    except Exception:
        pass
    if request:
        alternates = {
            key: _build_absolute_url(request, value) if value.startswith("/") else value
            for key, value in alternates.items()
        }

    return ResolvedMetadata(
        title=title,
        description=description,
        canonical=canonical,
        robots=robots,
        alternates=alternates,
        open_graph=open_graph,
        twitter=twitter,
        json_ld=json_ld,
    )


def auto_generate_meta_title(instance) -> str | None:
    """
    Auto-generate meta_title for a post if not manually set.
    Uses pattern: "Post Title - Site Name" (max 70 chars).

    Args:
        instance: Post or Page model instance

    Returns:
        Auto-generated meta_title string, or None if can't generate
    """
    if not hasattr(instance, "title"):
        return None

    site_seo = SiteSeoSettings.get_solo()
    site_name = site_seo.default_meta_title or "Blog"

    # Build candidate title
    base_title = instance.title[:50]
    candidate = f"{base_title} - {site_name}"[:70]

    return candidate if candidate else None


def auto_generate_meta_description(instance) -> str | None:
    """
    Auto-generate meta_description for a post if not manually set.
    Uses: excerpt > summary > first 160 chars of body (max 170 chars).

    Args:
        instance: Post or Page model instance

    Returns:
        Auto-generated meta_description string, or None if can't generate
    """
    candidates = []

    # Try excerpt first
    if hasattr(instance, "excerpt") and instance.excerpt:
        candidates.append(instance.excerpt[:170])

    # Try summary
    if hasattr(instance, "summary") and instance.summary:
        candidates.append(instance.summary[:170])

    # Try body markdown
    if hasattr(instance, "body_markdown") and instance.body_markdown:
        # Clean markdown syntax
        text = instance.body_markdown
        # Remove markdown headings
        text = __import__("re").sub(r"^#+\s+", "", text, flags=__import__("re").MULTILINE)
        # Remove markdown emphasis
        text = __import__("re").sub(r"[*_`]+", "", text)
        # Take first 170 chars
        candidates.append(text[:170])

    # Return first non-empty candidate
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip()

    return None


def generate_article_schema(post, canonical: str) -> dict[str, Any]:
    """
    Generate JSON-LD schema for a blog post (Article/NewsArticle type).

    Args:
        post: Post model instance
        canonical: Canonical URL for the post

    Returns:
        Dict representing the JSON-LD schema
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post.meta_title or post.title,
        "description": post.meta_description or "",
        "url": canonical,
    }

    # Add author
    if hasattr(post, "author") and post.author:
        schema["author"] = {
            "@type": "Person",
            "name": post.author.get_full_name() or post.author.username,
        }

    # Add dates
    if hasattr(post, "published_at") and post.published_at:
        schema["datePublished"] = post.published_at.isoformat()

    if hasattr(post, "updated_at") and post.updated_at:
        schema["dateModified"] = post.updated_at.isoformat()

    # Add cover image
    if hasattr(post, "cover_image") and post.cover_image:
        schema["image"] = post.cover_image.url

    # Add keywords from tags
    if hasattr(post, "tags") and post.tags.exists():
        schema["keywords"] = ", ".join([tag.name for tag in post.tags.all()])

    # Add article body
    if hasattr(post, "body_html") and post.body_html:
        schema["articleBody"] = post.body_html[:1000]  # First 1000 chars

    return schema


def generate_news_article_schema(post, canonical: str) -> dict[str, Any]:
    """
    Generate JSON-LD schema for a post as NewsArticle type.
    More specific variant of Article schema for news/timely content.

    Args:
        post: Post model instance
        canonical: Canonical URL for the post

    Returns:
        Dict representing the JSON-LD schema
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": post.meta_title or post.title,
        "description": post.meta_description or "",
        "url": canonical,
    }

    # Add author
    if hasattr(post, "author") and post.author:
        schema["author"] = {
            "@type": "Person",
            "name": post.author.get_full_name() or post.author.username,
        }

    # Add dates
    if hasattr(post, "published_at") and post.published_at:
        schema["datePublished"] = post.published_at.isoformat()

    if hasattr(post, "updated_at") and post.updated_at:
        schema["dateModified"] = post.updated_at.isoformat()

    # Add cover image
    if hasattr(post, "cover_image") and post.cover_image:
        schema["image"] = post.cover_image.url

    # Add headline variation (shorter version)
    base_title = post.title[:60]
    if base_title != post.title:
        schema["alternativeHeadline"] = base_title

    return schema


def apply_auto_metadata_to_instance(instance) -> None:
    """
    Apply auto-generated metadata fields to a model instance.
    Only sets fields that are not already manually set.

    Args:
        instance: Post or Page model instance
    """
    # Auto-generate meta_title if not set
    if not getattr(instance, "meta_title", None):
        auto_title = auto_generate_meta_title(instance)
        if auto_title and hasattr(instance, "meta_title"):
            instance.meta_title = auto_title

    # Auto-generate meta_description if not set
    if not getattr(instance, "meta_description", None):
        auto_desc = auto_generate_meta_description(instance)
        if auto_desc and hasattr(instance, "meta_description"):
            instance.meta_description = auto_desc


def generate_schema_markup(post, canonical: str, *, schema_type: str = "BlogPosting") -> dict[str, Any]:
    """
    Generate JSON-LD schema markup for a post.
    Wrapper that delegates to specific schema generators.

    Args:
        post: Post model instance
        canonical: Canonical URL
        schema_type: Type of schema ('BlogPosting' or 'NewsArticle')

    Returns:
        Dict representing the JSON-LD schema
    """
    if schema_type == "NewsArticle":
        return generate_news_article_schema(post, canonical)
    else:
        return generate_article_schema(post, canonical)
