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
    alternates: dict[str, Any]
    open_graph: dict[str, Any]
    twitter: dict[str, Any]
    json_ld: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_absolute_url(request: Any, path: str) -> str:
    if request is None:
        return path
    return request.build_absolute_uri(path)


def _canonical_from_base(base_url: str, path: str) -> str:
    if not base_url:
        return path
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _resolve_route_profile(route_name: str) -> SeoRouteProfile | None:
    if not route_name:
        return None
    return SeoRouteProfile.objects.filter(route_name=route_name, enabled=True).first()


def _organization_schema(site_settings: Any) -> dict[str, Any] | None:
    if not site_settings.organization_schema_name:
        return None
    org_url = site_settings.organization_schema_url or ""
    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": site_settings.organization_schema_name,
        "url": org_url,
    }
    logo_url = getattr(site_settings, "organization_logo_url", "") or ""
    if logo_url:
        schema["logo"] = logo_url
    same_as: list[str] = []
    for attr in ("twitter_site_handle", "facebook_url", "linkedin_url", "github_url"):
        val = getattr(site_settings, attr, "") or ""
        if val:
            same_as.append(val if val.startswith("http") else f"https://twitter.com/{val.lstrip('@')}")
    if same_as:
        schema["sameAs"] = same_as
    return schema


def _website_schema(site_settings: Any, base_url: str) -> dict[str, Any]:
    """WebSite schema with SearchAction for sitelinks search box."""
    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site_settings.default_meta_title or "Blog",
        "url": base_url.rstrip("/") + "/",
    }
    # SearchAction for Google sitelinks search box
    search_url = base_url.rstrip("/") + "/search/?q={search_term_string}"
    schema["potentialAction"] = {
        "@type": "SearchAction",
        "target": {"@type": "EntryPoint", "urlTemplate": search_url},
        "query-input": "required name=search_term_string",
    }
    return schema


def _breadcrumb_schema(adapter: Any, canonical: str, site_name: str) -> dict[str, Any]:
    """BreadcrumbList schema for navigation trail."""
    items: list[dict[str, Any]] = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": site_name or "Home",
            "item": canonical.split("//" , 1)[-1].split("/")[0] if "//" in canonical else "/",
        }
    ]
    # Build breadcrumb from URL path
    parts = [p for p in (adapter.url or "").strip("/").split("/") if p]
    base = canonical.rsplit(adapter.url or "/", 1)[0] if adapter.url else ""
    for i, part in enumerate(parts, start=2):
        item: dict[str, Any] = {
            "@type": "ListItem",
            "position": i,
            "name": part.replace("-", " ").title(),
        }
        # Only add item URL for non-terminal crumbs
        if i <= len(parts):
            crumb_path = "/".join(parts[:i - 1]) + "/"
            item["item"] = f"{base}/{crumb_path}"
        items.append(item)

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def _content_schema(adapter: Any, canonical: str) -> dict[str, Any]:
    """
    Rich content schema — BlogPosting with author, image, keywords
    or WebPage for pages.
    """
    if adapter.route_type == "post":
        schema: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": adapter.meta_title or adapter.title,
            "description": adapter.meta_description,
            "url": canonical,
        }
        if adapter.published_at:
            schema["datePublished"] = adapter.published_at.isoformat()
        if adapter.updated_at:
            schema["dateModified"] = adapter.updated_at.isoformat()
        if adapter.og_image_url:
            schema["image"] = adapter.og_image_url
        # Add author from the original instance (available via _original_instance)
        author_name = getattr(adapter, "_author_name", "") or ""
        if author_name:
            schema["author"] = {"@type": "Person", "name": author_name}
        # Add keywords from tags
        keywords_str = getattr(adapter, "_keywords_csv", "") or ""
        if keywords_str:
            schema["keywords"] = keywords_str
        return schema

    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": adapter.meta_title or adapter.title,
        "description": adapter.meta_description,
        "dateModified": adapter.updated_at.isoformat() if adapter.updated_at else None,
        "url": canonical,
    }


def _build_robots(site_seo: Any, *, noindex: bool = False) -> str:
    index_part = "noindex" if noindex else ("index" if site_seo.robots_index else "noindex")
    follow_part = "follow" if site_seo.robots_follow else "nofollow"
    return f"{index_part},{follow_part},max-snippet:-1,max-image-preview:large"


def resolve_metadata(adapter: Any, *, request: Any = None) -> ResolvedMetadata:
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
        "site_name": site_seo.default_meta_title or "",
        "locale": "en_US",
        "published_time": adapter.published_at.isoformat() if adapter.published_at else "",
        "modified_time": adapter.updated_at.isoformat() if adapter.updated_at else "",
    }
    # Article-specific OG fields
    if adapter.route_type == "post":
        author_name = getattr(adapter, "_author_name", "") or ""
        if author_name:
            open_graph["author"] = author_name
        section = getattr(adapter, "_section", "") or ""
        if section:
            open_graph["section"] = section
        tags_list = getattr(adapter, "_tag_names", []) or []
        if tags_list:
            open_graph["tags"] = tags_list

    twitter = {
        "card": "summary_large_image" if image_url else "summary",
        "title": title,
        "description": description,
        "image": image_url or "",
        "site": site_seo.twitter_site_handle or "",
        "creator": getattr(adapter, "_twitter_creator", "") or site_seo.twitter_site_handle or "",
    }

    json_ld: list[dict[str, Any]] = []
    org_schema = _organization_schema(site_seo)
    if org_schema:
        json_ld.append(org_schema)

    # WebSite + SearchAction schema (always present)
    base_url = site_seo.canonical_base_url or ""
    if base_url:
        json_ld.append(_website_schema(site_seo, base_url))

    # Content schema (BlogPosting or WebPage)
    json_ld.append(_content_schema(adapter, canonical))

    # BreadcrumbList schema
    site_name = site_seo.default_meta_title or "Home"
    json_ld.append(_breadcrumb_schema(adapter, canonical, site_name))

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


def auto_generate_meta_title(instance: Any) -> str | None:
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


def auto_generate_meta_description(instance: Any) -> str | None:
    """
    Auto-generate meta_description for a post if not manually set.
    Uses: excerpt > summary > first 160 chars of body (max 170 chars).

    Args:
        instance: Post or Page model instance

    Returns:
        Auto-generated meta_description string, or None if can't generate
    """
    candidates: list[str] = []

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


def generate_article_schema(post: Any, canonical: str) -> dict[str, Any]:
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


def generate_news_article_schema(post: Any, canonical: str) -> dict[str, Any]:
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


def apply_auto_metadata_to_instance(instance: Any) -> dict[str, str]:
    """
    Apply auto-generated metadata fields to a model instance.
    Now ALWAYS evaluates and fixes suboptimal values, not just empty ones.
    Respects SeoMetadataLock — locked fields are never touched.

    Returns dict of {field_name: old_value} for fields that were changed.
    """
    from .models import SeoMetadataLock

    changes: dict[str, str] = {}
    ct = None
    try:
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(instance.__class__)
    except Exception:
        pass

    lock = None
    if ct and getattr(instance, "pk", None):
        lock = SeoMetadataLock.objects.filter(
            content_type=ct, object_id=instance.pk,
        ).first()

    # ── Meta title: fill if empty OR fix if bad length ──────────────────
    if hasattr(instance, "meta_title") and not (lock and lock.lock_title):
        current_title = getattr(instance, "meta_title", "") or ""
        needs_fix = False
        if not current_title or len(current_title) > 70 or len(current_title) < 20:
            needs_fix = True

        if needs_fix:
            auto_title = auto_generate_meta_title(instance)
            if auto_title and auto_title != current_title:
                changes["meta_title"] = current_title
                instance.meta_title = auto_title

    # ── Meta description: fill if empty OR fix if bad length ────────────
    if hasattr(instance, "meta_description") and not (lock and lock.lock_description):
        current_desc = getattr(instance, "meta_description", "") or ""
        needs_fix = False
        if not current_desc or len(current_desc) > 170 or len(current_desc) < 60:
            needs_fix = True

        if needs_fix:
            auto_desc = auto_generate_meta_description(instance)
            if auto_desc and auto_desc != current_desc:
                changes["meta_description"] = current_desc
                instance.meta_description = auto_desc

    # ── Canonical URL: fill if empty, fix if relative ───────────────────
    if hasattr(instance, "canonical_url") and not (lock and lock.lock_canonical):
        current_canonical = getattr(instance, "canonical_url", "") or ""
        needs_fix = False
        if not current_canonical or not _is_absolute_url(current_canonical):
            needs_fix = True

        if needs_fix:
            auto_canonical = _auto_generate_canonical(instance)
            if auto_canonical and auto_canonical != current_canonical:
                changes["canonical_url"] = current_canonical
                instance.canonical_url = auto_canonical

    return changes


def _is_absolute_url(url: str) -> bool:
    """Check if URL has scheme and netloc."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def _auto_generate_canonical(instance: Any) -> str:
    """Generate absolute canonical URL from SeoSettings.canonical_base_url + get_absolute_url()."""
    try:
        path = instance.get_absolute_url()
    except Exception:
        return ""
    if not path:
        return ""

    site_seo = SiteSeoSettings.get_solo()
    base_url = getattr(site_seo, "canonical_base_url", "") or ""

    if base_url:
        return _canonical_from_base(base_url, path)

    # Fallback: try to build from Django sites framework
    try:
        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()
        return f"https://{current_site.domain}{path}"
    except Exception:
        pass

    return ""


def generate_schema_markup(post: Any, canonical: str, *, schema_type: str = "BlogPosting") -> dict[str, Any]:
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
