from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

TOKEN_RE = re.compile(r"[a-zA-Z0-9]{3,}")
H1_RE = re.compile(r"<h1[^>]*>", re.IGNORECASE)
IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ALT_RE = re.compile(r'alt\s*=\s*"([^"]*)"|alt\s*=\s*\'([^\']*)\'', re.IGNORECASE)
LINK_RE = re.compile(r"<a\b[^>]*href\s*=\s*\"([^\"]+)\"|<a\b[^>]*href\s*=\s*'([^']+)'", re.IGNORECASE)

COMMON_STOP_WORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "that",
    "this",
    "your",
    "into",
    "about",
    "over",
    "under",
    "while",
    "where",
}


@dataclass
class CheckResult:
    key: str
    severity: str
    passed: bool
    message: str
    suggested_fix: str = ""
    autofixable: bool = False
    related_field: str = ""
    details: dict[str, Any] = field(default_factory=lambda: {})


def _tokens(text: str) -> list[str]:
    if not text:
        return []
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if token.lower() not in COMMON_STOP_WORDS
    ]


def _focus_term(adapter: Any) -> str:
    candidates = _tokens(
        " ".join(
            part for part in [adapter.title, adapter.meta_title, adapter.meta_description] if part
        )
    )
    return candidates[0] if candidates else ""


def _is_absolute_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def _extract_links(html: str) -> list[str]:
    links: list[str] = []
    for pair in LINK_RE.findall(html or ""):
        href = pair[0] or pair[1]
        if href:
            links.append(href.strip())
    return links


def _extract_internal_links(html: str) -> list[str]:
    links = _extract_links(html)
    return [link for link in links if link.startswith("/") or "://" not in link]


def _extract_external_links(html: str) -> list[str]:
    links = _extract_links(html)
    return [link for link in links if link.startswith("http://") or link.startswith("https://")]


def _extract_image_tags(html: str) -> list[str]:
    return IMG_RE.findall(html or "")


def _extract_alt_value(img_tag: str) -> str:
    match = ALT_RE.search(img_tag)
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def _has_schema(metadata: dict[str, Any]) -> bool:
    json_ld: list[Any] = metadata.get("json_ld") or []
    return bool(json_ld)


def _is_indexable(metadata: dict[str, Any]) -> bool:
    robots = (metadata.get("robots") or "").replace(" ", "").lower()
    if not robots:
        return True
    return "noindex" not in robots


def _estimate_cannibalization(adapter: Any) -> int:
    title = (adapter.title or "").strip()
    if not title:
        return 0
    queryset = adapter.model.objects.exclude(pk=adapter.pk)
    return queryset.filter(
        Q(title__iexact=title)
        | Q(slug__iexact=adapter.slug)
    ).count()


def run_checks(adapter: Any, metadata: dict[str, Any], *, min_internal_links: int = 3) -> list[CheckResult]:
    focus = _focus_term(adapter)
    title = (metadata.get("title") or adapter.title or "").strip()
    description = (metadata.get("description") or "").strip()
    canonical = (metadata.get("canonical") or "").strip()
    body_html = adapter.body_html or ""
    body_markdown = adapter.body_markdown or ""
    word_count = adapter.word_count or max(len(_tokens(body_markdown)), 0)
    title_tokens = set(_tokens(title))
    intro_text = " ".join((body_markdown or "").split()[:80])
    heading_text = " ".join(re.findall(r"^\s{0,3}#{1,6}\s+(.+)$", body_markdown, flags=re.MULTILINE))

    internal_links = _extract_internal_links(body_html)
    external_links = _extract_external_links(body_html)
    img_tags = _extract_image_tags(body_html)
    alt_count = sum(1 for tag in img_tags if _extract_alt_value(tag))

    results: list[CheckResult] = []

    results.append(
        CheckResult(
            key="title_present",
            severity="critical",
            passed=bool(title),
            message="Title is present." if title else "Title is missing.",
            suggested_fix="Provide a clear SEO title.",
            autofixable=True,
        )
    )
    results.append(
        CheckResult(
            key="title_length_range",
            severity="warning",
            passed=20 <= len(title) <= 70,
            message=f"Title length is {len(title)} chars.",
            suggested_fix="Target 20-70 characters.",
            autofixable=True,
        )
    )
    duplicate_titles = adapter.model.objects.exclude(pk=adapter.pk).filter(meta_title__iexact=title).count()
    results.append(
        CheckResult(
            key="title_uniqueness_global",
            severity="warning",
            passed=duplicate_titles == 0,
            message="Title appears unique." if duplicate_titles == 0 else f"{duplicate_titles} similar titles found.",
            suggested_fix="Differentiate title from existing pages/posts.",
            details={"duplicate_count": duplicate_titles},
        )
    )
    results.append(
        CheckResult(
            key="meta_description_present",
            severity="critical",
            passed=bool(description),
            message="Meta description present." if description else "Meta description missing.",
            suggested_fix="Set concise meta description.",
            autofixable=True,
        )
    )
    results.append(
        CheckResult(
            key="meta_description_length_range",
            severity="warning",
            passed=60 <= len(description) <= 170,
            message=f"Description length is {len(description)} chars.",
            suggested_fix="Target 60-170 characters.",
            autofixable=True,
        )
    )
    results.append(
        CheckResult(
            key="canonical_present_or_resolvable",
            severity="critical",
            passed=bool(canonical),
            message="Canonical URL set." if canonical else "Canonical URL missing.",
            suggested_fix="Provide canonical URL.",
            autofixable=True,
        )
    )
    results.append(
        CheckResult(
            key="canonical_valid_absolute",
            severity="critical",
            passed=_is_absolute_url(canonical),
            message="Canonical URL is absolute." if _is_absolute_url(canonical) else "Canonical URL must be absolute.",
            suggested_fix="Use absolute URL with scheme and host.",
            autofixable=True,
        )
    )
    slug = (adapter.slug or "").strip()
    slug_ok = bool(slug and len(slug) <= 90 and "_" not in slug)
    results.append(
        CheckResult(
            key="slug_quality",
            severity="warning",
            passed=slug_ok,
            message="Slug looks clean." if slug_ok else "Slug quality can be improved.",
            suggested_fix="Use concise lowercase hyphenated slug.",
        )
    )
    h1_count = len(H1_RE.findall(body_html))
    results.append(
        CheckResult(
            key="single_h1",
            severity="warning",
            passed=h1_count <= 1,
            message="Single H1 detected." if h1_count <= 1 else f"{h1_count} H1 headings found.",
            suggested_fix="Use one H1 per page.",
            details={"h1_count": h1_count},
        )
    )
    results.append(
        CheckResult(
            key="content_min_word_count",
            severity="warning",
            passed=word_count >= 220,
            message=f"Content word count is {word_count}.",
            suggested_fix="Expand content depth when useful.",
        )
    )
    results.append(
        CheckResult(
            key="focus_term_in_title",
            severity="warning",
            passed=not focus or focus in title_tokens,
            message="Focus term appears in title." if (not focus or focus in title_tokens) else "Focus term missing in title.",
            suggested_fix="Include focus term naturally in title.",
        )
    )
    results.append(
        CheckResult(
            key="focus_term_in_intro",
            severity="warning",
            passed=not focus or focus in _tokens(intro_text),
            message="Focus term appears in intro." if (not focus or focus in _tokens(intro_text)) else "Focus term missing in intro.",
            suggested_fix="Include focus term in opening paragraph.",
        )
    )
    results.append(
        CheckResult(
            key="focus_term_in_heading",
            severity="warning",
            passed=not focus or focus in _tokens(heading_text),
            message="Focus term appears in heading." if (not focus or focus in _tokens(heading_text)) else "Focus term missing in headings.",
            suggested_fix="Add focus term to at least one heading.",
        )
    )
    alt_ok = not img_tags or alt_count == len(img_tags)
    results.append(
        CheckResult(
            key="image_alt_coverage",
            severity="warning",
            passed=alt_ok,
            message="All images contain alt text." if alt_ok else f"{alt_count}/{len(img_tags)} images have alt text.",
            suggested_fix="Add descriptive alt text for all images.",
        )
    )
    results.append(
        CheckResult(
            key="internal_links_minimum",
            severity="warning",
            passed=len(internal_links) >= min_internal_links,
            message=f"{len(internal_links)} internal links detected.",
            suggested_fix=f"Add at least {min_internal_links} relevant internal links.",
        )
    )
    results.append(
        CheckResult(
            key="internal_links_not_broken",
            severity="warning",
            passed=all(link.startswith("/") or link.startswith("http") for link in internal_links),
            message="Internal links look valid.",
            suggested_fix="Review malformed internal links.",
        )
    )
    external_ok = True
    for link in external_links:
        if not link.startswith("http"):
            external_ok = False
            break
    results.append(
        CheckResult(
            key="external_links_rel_policy",
            severity="info",
            passed=external_ok,
            message="External links policy is acceptable." if external_ok else "External links policy needs review.",
            suggested_fix="Ensure outbound links use safe rel policy.",
        )
    )
    og: dict[str, Any] = metadata.get("open_graph") or {}
    og_ok = bool(og.get("title") and og.get("description") and og.get("url"))
    results.append(
        CheckResult(
            key="open_graph_complete",
            severity="warning",
            passed=og_ok,
            message="Open Graph metadata complete." if og_ok else "Open Graph metadata incomplete.",
            suggested_fix="Provide OG title, description, and URL.",
            autofixable=True,
        )
    )
    tw: dict[str, Any] = metadata.get("twitter") or {}
    tw_ok = bool(tw.get("card") and tw.get("title") and tw.get("description"))
    results.append(
        CheckResult(
            key="twitter_card_complete",
            severity="warning",
            passed=tw_ok,
            message="Twitter metadata complete." if tw_ok else "Twitter metadata incomplete.",
            suggested_fix="Set twitter card/title/description.",
            autofixable=True,
        )
    )
    schema_ok = _has_schema(metadata)
    results.append(
        CheckResult(
            key="schema_presence_valid",
            severity="warning",
            passed=schema_ok,
            message="Structured data present." if schema_ok else "Structured data missing.",
            suggested_fix="Add JSON-LD schema.",
            autofixable=True,
        )
    )
    robots = (metadata.get("robots") or "").lower()
    robots_ok = bool(robots)
    results.append(
        CheckResult(
            key="robots_directive_consistency",
            severity="warning",
            passed=robots_ok,
            message="Robots directive set." if robots_ok else "Robots directive missing.",
            suggested_fix="Set robots directive explicitly.",
            autofixable=True,
        )
    )
    in_sitemap = _is_indexable(metadata)
    results.append(
        CheckResult(
            key="sitemap_membership_and_lastmod",
            severity="warning",
            passed=in_sitemap and bool(adapter.updated_at),
            message="Sitemap eligibility is healthy." if in_sitemap else "Route may be excluded from sitemap by robots policy.",
            suggested_fix="Ensure indexable pages can appear in sitemap.",
        )
    )

    # Orphan estimate uses previously generated edges only.
    source_ct = ContentType.objects.get_for_model(adapter.model)
    outgoing_edges = adapter.link_edge_model.objects.filter(
        source_content_type=source_ct,
        source_object_id=adapter.pk,
        status="applied",
    ).count()
    incoming_edges = adapter.link_edge_model.objects.filter(
        target_content_type=source_ct,
        target_object_id=adapter.pk,
        status="applied",
    ).count()
    orphan_risk_ok = outgoing_edges > 0 or incoming_edges > 0
    results.append(
        CheckResult(
            key="orphan_or_cannibalization_risk",
            severity="warning",
            passed=orphan_risk_ok and _estimate_cannibalization(adapter) == 0,
            message="No orphan/cannibalization red flag." if (orphan_risk_ok and _estimate_cannibalization(adapter) == 0) else "Potential orphan or cannibalization risk.",
            suggested_fix="Add internal links and differentiate overlapping titles/slugs.",
            details={
                "outgoing_edges": outgoing_edges,
                "incoming_edges": incoming_edges,
                "cannibalization_candidates": _estimate_cannibalization(adapter),
            },
        )
    )

    # ── Map checks to form fields for inline display ────────────────────────
    _FIELD_MAP: dict[str, str] = {
        "title_present": "title",
        "title_length_range": "title",
        "title_uniqueness_global": "title",
        "focus_term_in_title": "title",
        "meta_description_present": "meta_description",
        "meta_description_length_range": "meta_description",
        "canonical_present_or_resolvable": "canonical_url",
        "canonical_valid_absolute": "canonical_url",
        "slug_quality": "slug",
        "single_h1": "body_markdown",
        "content_min_word_count": "body_markdown",
        "focus_term_in_intro": "body_markdown",
        "focus_term_in_heading": "body_markdown",
        "image_alt_coverage": "body_markdown",
        "internal_links_minimum": "body_markdown",
        "internal_links_not_broken": "body_markdown",
        "external_links_rel_policy": "body_markdown",
        "open_graph_complete": "meta_title",
        "twitter_card_complete": "meta_title",
        "schema_presence_valid": "",
        "robots_directive_consistency": "",
        "sitemap_membership_and_lastmod": "",
        "orphan_or_cannibalization_risk": "",
    }
    for result in results:
        result.related_field = _FIELD_MAP.get(result.key, "")

    return results
