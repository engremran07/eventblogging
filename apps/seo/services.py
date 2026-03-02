from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count
from django.utils import timezone

from blog.models import Post
from pages.models import Page

from .checks import run_checks
from .interlink import (
    apply_suggestions_to_markdown,
    build_interlink_suggestions,
    compute_link_budget,
)
from .metadata import resolve_metadata
from .models import (
    SeoAuditSnapshot,
    SeoEngineSettings,
    SeoIssue,
    SeoLinkEdge,
    SeoMetadataLock,
    SeoRedirectRule,
    SeoSuggestion,
)

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[a-zA-Z0-9]{2,}")


@dataclass
class ContentAdapter:
    pk: int
    model: type
    content_type: ContentType
    route_type: str
    title: str
    slug: str
    meta_title: str
    meta_description: str
    canonical_url: str
    body_markdown: str
    body_html: str
    word_count: int
    created_at: timezone.datetime | None
    updated_at: timezone.datetime | None
    published_at: timezone.datetime | None
    url: str
    summary: str
    excerpt: str
    og_image_url: str
    is_featured: bool
    status: str
    link_edge_model: type = SeoLinkEdge

    # Rich metadata fields (populated from instance for schema/OG)
    _author_name: str = ""
    _keywords_csv: str = ""
    _section: str = ""
    _tag_names: list[str] = field(default_factory=list)
    _twitter_creator: str = ""

    @property
    def excerpt_or_summary(self) -> str:
        return self.excerpt or self.summary

    @property
    def is_published(self) -> bool:
        return (
            self.status == "published"
            and self.published_at is not None
            and self.published_at <= timezone.now()
        )

    def get_absolute_url(self) -> str:
        return self.url


def _content_type_for_instance(instance: Any) -> ContentType:
    return ContentType.objects.get_for_model(instance.__class__)


def _build_adapter_from_instance(instance: Any) -> ContentAdapter:
    route_type = "other"
    summary = ""
    excerpt = ""
    og_image_url = ""
    author_name = ""
    keywords_csv = ""
    section = ""
    tag_names: list[str] = []

    if isinstance(instance, Post):
        route_type = "post"
        excerpt = instance.excerpt or ""
        if instance.cover_image:
            og_image_url = instance.cover_image.url
        # Rich metadata for schema/OG
        if hasattr(instance, "author") and instance.author:
            author_name = instance.author.get_full_name() or instance.author.username
        try:
            tag_names = [t.name for t in instance.tags.all()]  # type: ignore[union-attr]
            keywords_csv = ", ".join(tag_names)
        except Exception:
            pass
        try:
            if instance.primary_topic:
                section = str(instance.primary_topic)
        except Exception:
            pass
    elif isinstance(instance, Page):
        route_type = "page"
        summary = instance.summary or ""

    return ContentAdapter(
        pk=instance.pk,
        model=instance.__class__,
        content_type=_content_type_for_instance(instance),
        route_type=route_type,
        title=instance.title or "",
        slug=instance.slug or "",
        meta_title=getattr(instance, "meta_title", "") or "",
        meta_description=getattr(instance, "meta_description", "") or "",
        canonical_url=getattr(instance, "canonical_url", "") or "",
        body_markdown=instance.body_markdown or "",
        body_html=instance.body_html or "",
        word_count=getattr(instance, "word_count", 0) or 0,
        created_at=getattr(instance, "created_at", None),
        updated_at=getattr(instance, "updated_at", None),
        published_at=getattr(instance, "published_at", None),
        url=instance.get_absolute_url(),
        summary=summary,
        excerpt=excerpt,
        og_image_url=og_image_url,
        is_featured=bool(getattr(instance, "is_featured", False)),
        status=getattr(instance, "status", "") or "",
        _author_name=author_name,
        _keywords_csv=keywords_csv,
        _section=section,
        _tag_names=tag_names,
    )


def build_adapter_from_instance(instance: Any) -> ContentAdapter:
    return _build_adapter_from_instance(instance)


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _clip(text: str, limit: int) -> str:
    return _normalize_text(text)[:limit]


def build_route_adapter(
    *,
    route_type: str,
    title: str,
    description: str = "",
    body_markdown: str = "",
    url: str = "/",
    updated_at: Any = None,
    published_at: Any = None,
    canonical_url: str = "",
    og_image_url: str = "",
) -> ContentAdapter:
    model = Page if route_type in {"page", "policy"} else Post
    content_type = ContentType.objects.get_for_model(model)
    safe_title = _clip(title, 220) or "Untitled"
    safe_description = _clip(description, 320)
    body = body_markdown or ""
    word_count = max(len(TOKEN_RE.findall(body)), 0)
    now = timezone.now()
    return ContentAdapter(
        pk=0,
        model=model,
        content_type=content_type,
        route_type=route_type,
        title=safe_title,
        slug="",
        meta_title=safe_title[:70],
        meta_description=safe_description[:170],
        canonical_url=canonical_url,
        body_markdown=body,
        body_html="",
        word_count=word_count,
        created_at=updated_at or now,
        updated_at=updated_at or now,
        published_at=published_at,
        url=url or "/",
        summary=safe_description,
        excerpt=safe_description,
        og_image_url=og_image_url or "",
        is_featured=False,
        status="published" if published_at else "draft",
    )


def resolve_metadata_for_instance(instance: Any, *, request: Any = None) -> dict[str, Any]:
    adapter = _build_adapter_from_instance(instance)
    return resolve_metadata(adapter, request=request).to_dict()


def resolve_metadata_for_route(
    request: Any,
    *,
    route_type: str,
    title: str,
    description: str = "",
    body_markdown: str = "",
    canonical_url: str = "",
    og_image_url: str = "",
) -> dict[str, Any]:
    adapter = build_route_adapter(
        route_type=route_type,
        title=title,
        description=description,
        body_markdown=body_markdown,
        url=request.path if request else "/",
        canonical_url=canonical_url,
        og_image_url=og_image_url,
        updated_at=timezone.now(),
        published_at=timezone.now(),
    )
    return resolve_metadata(adapter, request=request).to_dict()


def metadata_template_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    metadata = metadata or {}
    json_ld: list[Any] = metadata.get("json_ld") or []
    json_ld_serialized = [
        json.dumps(node, ensure_ascii=False, separators=(",", ":")) for node in json_ld
    ]
    return {
        "resolved_seo": metadata,
        "resolved_seo_json_ld": json_ld_serialized,
    }


def seo_context_for_instance(instance: Any, *, request: Any = None) -> dict[str, Any]:
    return metadata_template_payload(resolve_metadata_for_instance(instance, request=request))


def seo_context_for_route(
    request: Any,
    *,
    route_type: str,
    title: str,
    description: str = "",
    body_markdown: str = "",
    canonical_url: str = "",
    og_image_url: str = "",
):
    metadata = resolve_metadata_for_route(
        request,
        route_type=route_type,
        title=title,
        description=description,
        body_markdown=body_markdown,
        canonical_url=canonical_url,
        og_image_url=og_image_url,
    )
    return metadata_template_payload(metadata)


# ---------------------------------------------------------------------------
# Content signal computation
# ---------------------------------------------------------------------------

_VOWELS = set("aeiouAEIOU")
_SYLLABLE_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_HEADING_HTML_RE = re.compile(r"<h[1-6][^>]*>", re.IGNORECASE)
_IMG_HTML_RE = re.compile(r"<img\b", re.IGNORECASE)
_INTERNAL_LINK_RE = re.compile(
    r'<a\b[^>]*\bhref\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")

# Search-intent keyword sets
_INTENT_INFORMATIONAL = frozenset({
    "how", "what", "why", "when", "where", "guide", "tutorial",
    "learn", "explain", "understand", "definition", "meaning",
    "example", "examples", "tips", "introduction",
})
_INTENT_TRANSACTIONAL = frozenset({
    "buy", "price", "deal", "discount", "order", "shop", "purchase",
    "coupon", "cheap", "sale", "offer", "subscribe", "download",
})
_INTENT_COMMERCIAL = frozenset({
    "best", "review", "compare", "comparison", "top", "versus", "vs",
    "alternative", "alternatives", "ranking", "rated", "recommended",
})
_INTENT_NAVIGATIONAL = frozenset({
    "login", "signin", "sign-in", "signup", "sign-up", "account",
    "dashboard", "portal", "official", "homepage",
})


def _count_syllables(word: str) -> int:
    """Estimate syllable count using vowel-group heuristic."""
    word = word.lower().strip()
    if not word:
        return 0
    count = len(_SYLLABLE_RE.findall(word))
    # Silent-e adjustment
    if word.endswith("e") and count > 1:
        count -= 1
    # Minimum 1 syllable per word
    return max(count, 1)


def _compute_flesch_kincaid(text: str) -> int:
    """
    Compute Flesch-Kincaid Reading Ease score (0-100).
    Higher = easier to read.
    Formula: 206.835 - 1.015*(words/sentences) - 84.6*(syllables/words)
    """
    if not text:
        return 0
    # Strip markdown syntax
    clean = re.sub(r"[#*_`\[\]()>~|\\-]+", " ", text)
    words = [w for w in clean.split() if len(w) > 0]
    total_words = len(words)
    if total_words < 10:
        return 0
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(clean) if len(s.strip()) > 5]
    total_sentences = max(len(sentences), 1)
    total_syllables = sum(_count_syllables(w) for w in words)

    score = 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
    return max(0, min(100, round(score)))


def _extract_focus_term(instance: Any) -> str:
    """Extract the dominant focus term from title + meta_title."""
    title = getattr(instance, "title", "") or ""
    meta_title = getattr(instance, "meta_title", "") or ""
    combined = f"{title} {meta_title}"
    tokens = TOKEN_RE.findall(combined.lower())
    if not tokens:
        return ""
    # Return the most frequent non-stop-word token
    from collections import Counter
    stop = {"and", "the", "for", "with", "from", "that", "this", "your", "into",
            "about", "over", "under", "while", "where", "are", "was", "been",
            "have", "has", "had", "will", "can", "not", "but", "all"}
    filtered = [t for t in tokens if t not in stop and len(t) > 2]
    if not filtered:
        return tokens[0] if tokens else ""
    counts = Counter(filtered)
    return counts.most_common(1)[0][0]


def _compute_keyword_density(text: str, focus_term: str) -> float:
    """Compute focus keyword density as a percentage."""
    if not text or not focus_term:
        return 0.0
    words = text.lower().split()
    total = len(words)
    if total == 0:
        return 0.0
    occurrences = sum(1 for w in words if focus_term in w)
    return round((occurrences / total) * 100, 2)


def _compute_thin_content_score(word_count: int, heading_count: int, image_count: int) -> int:
    """
    Compute thin content score (0-10). Higher = thinner content.
    0 = rich content, 10 = severely thin.
    """
    score = 0
    if word_count < 100:
        score += 6
    elif word_count < 300:
        score += 4
    elif word_count < 500:
        score += 2
    elif word_count < 800:
        score += 1

    if heading_count == 0:
        score += 2
    if image_count == 0:
        score += 1
    # No structural variety (very few headings for long content)
    if word_count > 500 and heading_count < 2:
        score += 1

    return min(score, 10)


def _classify_search_intent(title: str) -> str:
    """Classify search intent from title keywords."""
    if not title:
        return "informational"
    words = set(title.lower().split())
    # Check each intent category
    if words & _INTENT_TRANSACTIONAL:
        return "transactional"
    if words & _INTENT_COMMERCIAL:
        return "commercial"
    if words & _INTENT_NAVIGATIONAL:
        return "navigational"
    # Default to informational
    return "informational"


def compute_content_signals(instance: Any) -> None:
    """
    Compute and persist all SEO content signals for a Post or Page.
    Called from the signal pipeline after save.

    Signals computed:
    - flesch_score: Flesch-Kincaid readability (0-100)
    - keyword_density: Focus keyword density percentage
    - heading_count: Number of headings in body HTML
    - image_count: Number of images in body HTML
    - internal_link_count: Outbound internal links in body
    - inbound_link_count: Links pointing TO this content
    - is_orphan: True if no inbound links
    - thin_content_score: Content thinness indicator (0-10)
    - search_intent: Classified search intent
    - seo_audit_score: Written back from latest audit snapshot
    """
    from decimal import Decimal as D

    body_html = getattr(instance, "body_html", "") or ""
    body_markdown = getattr(instance, "body_markdown", "") or ""
    word_count = getattr(instance, "word_count", 0) or max(len(body_markdown.split()), 1)

    # --- Flesch-Kincaid readability ---
    flesch = _compute_flesch_kincaid(body_markdown)

    # --- Keyword density ---
    focus = _extract_focus_term(instance)
    density = _compute_keyword_density(body_markdown, focus)

    # --- Content counts from HTML ---
    heading_count = len(_HEADING_HTML_RE.findall(body_html))
    image_count = len(_IMG_HTML_RE.findall(body_html))

    internal_links = _INTERNAL_LINK_RE.findall(body_html)
    internal_link_count = sum(
        1 for link in internal_links
        if link.startswith("/") or "://" not in link
    )

    # --- Inbound links from SeoLinkEdge ---
    ct = _content_type_for_instance(instance)
    inbound_link_count = SeoLinkEdge.objects.filter(
        target_content_type=ct,
        target_object_id=instance.pk,
        status=SeoLinkEdge.Status.APPLIED,
    ).count()
    is_orphan = inbound_link_count == 0

    # --- Thin content score ---
    thin_score = _compute_thin_content_score(word_count, heading_count, image_count)

    # --- Search intent ---
    search_intent = _classify_search_intent(getattr(instance, "title", "") or "")

    # --- Build update dict (only fields the model has) ---
    signal_values: dict[str, Any] = {
        "flesch_score": flesch,
        "keyword_density": D(str(round(density, 2))),
        "heading_count": heading_count,
        "image_count": image_count,
        "internal_link_count": internal_link_count,
        "inbound_link_count": inbound_link_count,
        "is_orphan": is_orphan,
        "thin_content_score": min(thin_score, 10),
        "search_intent": search_intent,
    }

    changed_fields: list[str] = []
    for field_name, value in signal_values.items():
        if not hasattr(instance, field_name):
            continue
        current = getattr(instance, field_name, None)
        if current != value:
            setattr(instance, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        instance._seo_skip_signal = True  # type: ignore[union-attr]
        try:
            instance.save(update_fields=[*changed_fields, "updated_at"])
        finally:
            instance._seo_skip_signal = False  # type: ignore[union-attr]


def compute_tfidf_signals(instance: Any) -> None:
    """
    Compute TF-IDF keyword extraction and persist to model fields.
    Only runs for Post instances (Pages don't have the full TF-IDF pipeline).
    """
    if not isinstance(instance, Post):
        return
    if not getattr(instance, "body_html", ""):
        return

    try:
        from .tfidf import PostTfidfExtractor

        extractor = PostTfidfExtractor()
        keywords = extractor.extract_keywords(instance, top_n=15)
        if not keywords:
            return

        tfidf_vector = {kw["term"]: round(kw["score"], 4) for kw in keywords}

        # Build keyword_index: term → list of anchor-friendly variants
        keyword_index: dict[str, list[str]] = {}
        for kw in keywords:
            term = kw["term"]
            variants = [term, term.title()]
            if " " not in term:
                variants.append(term.capitalize())
            keyword_index[term] = variants

        changed_fields: list[str] = []
        if instance.tfidf_vector != tfidf_vector:
            instance.tfidf_vector = tfidf_vector
            changed_fields.append("tfidf_vector")
        if instance.keyword_index != keyword_index:
            instance.keyword_index = keyword_index
            changed_fields.append("keyword_index")

        if changed_fields:
            instance._seo_skip_signal = True
            try:
                instance.save(update_fields=[*changed_fields, "updated_at"])
            finally:
                instance._seo_skip_signal = False
    except Exception:
        logger.warning(
            "TF-IDF signal computation failed for post pk=%s",
            instance.pk,
            exc_info=True,
        )


def write_back_audit_score(instance: Any, snapshot: SeoAuditSnapshot) -> None:
    """
    Write the latest audit score and results back to the model instance.
    """
    if not snapshot:
        return

    changed_fields: list[str] = []
    score = round(snapshot.score)

    if hasattr(instance, "seo_audit_score") and instance.seo_audit_score != score:
        instance.seo_audit_score = score
        changed_fields.append("seo_audit_score")

    # Serialize issue details
    issues = list(
        SeoIssue.objects.filter(snapshot=snapshot).values(
            "check_key", "severity", "message", "suggested_fix", "autofixable"
        )
    )
    if hasattr(instance, "seo_audit_results") and instance.seo_audit_results != issues:
        instance.seo_audit_results = issues
        changed_fields.append("seo_audit_results")

    if changed_fields:
        instance._seo_skip_signal = True  # type: ignore[union-attr]
        try:
            instance.save(update_fields=[*changed_fields, "updated_at"])
        finally:
            instance._seo_skip_signal = False  # type: ignore[union-attr]


def _get_instance(content_type: str, object_id: int) -> Post | Page | None:
    if content_type == "post":
        return Post.objects.filter(pk=object_id).first()
    if content_type == "page":
        return Page.objects.filter(pk=object_id).first()  # type: ignore[return-value]
    return None


def _serialize_check_result(result: Any) -> dict[str, Any]:
    return {
        "key": result.key,
        "severity": result.severity,
        "passed": result.passed,
        "message": result.message,
        "suggested_fix": result.suggested_fix,
        "autofixable": result.autofixable,
        "related_field": getattr(result, "related_field", ""),
        "details": result.details,
    }


def _score_from_results(results: list[Any]) -> dict[str, Any]:
    total = len(results) or 1
    passed = sum(1 for row in results if row.passed)
    critical_count = sum(1 for row in results if not row.passed and row.severity == "critical")
    warning_count = sum(1 for row in results if not row.passed and row.severity == "warning")
    failed_count = total - passed
    score = (passed / total) * 100.0
    score -= critical_count * 6.0
    score -= warning_count * 2.0
    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 2),
        "passed_count": passed,
        "failed_count": failed_count,
        "critical_count": critical_count,
        "warning_count": warning_count,
    }


def _checksum(adapter: ContentAdapter, metadata: dict[str, Any], results: list[Any]) -> str:
    payload = {
        "id": f"{adapter.route_type}:{adapter.pk}",
        "updated_at": adapter.updated_at.isoformat() if adapter.updated_at else "",
        "meta": metadata,
        "results": [_serialize_check_result(row) for row in results],
    }
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _target_pool(source_adapter: ContentAdapter) -> list[ContentAdapter]:
    targets: list[ContentAdapter] = []
    for post in Post.objects.published().only(
        "id",
        "title",
        "excerpt",
        "slug",
        "body_markdown",
        "body_html",
        "word_count",
        "published_at",
        "updated_at",
        "created_at",
        "status",
        "is_featured",
    )[:250]:
        if source_adapter.route_type == "post" and source_adapter.pk == post.pk:
            continue
        targets.append(_build_adapter_from_instance(post))
    for page in Page.objects.published().only(  # type: ignore[attr-defined]
        "id",
        "title",
        "summary",
        "slug",
        "body_markdown",
        "body_html",
        "word_count",
        "published_at",
        "updated_at",
        "created_at",
        "status",
        "is_featured",
    )[:250]:
        if source_adapter.route_type == "page" and source_adapter.pk == page.pk:
            continue
        targets.append(_build_adapter_from_instance(page))
    return targets


def _build_metadata_suggestion(adapter: ContentAdapter, metadata: dict[str, Any]) -> None:
    payload = {
        "meta_title": metadata.get("title", "")[:70],
        "meta_description": metadata.get("description", "")[:170],
        "canonical_url": metadata.get("canonical", ""),
    }
    SeoSuggestion.objects.create(
        content_type=adapter.content_type,
        object_id=adapter.pk,
        suggestion_type=SeoSuggestion.SuggestionType.METADATA,
        payload_json=payload,
        confidence=0.86,
    )


def _metadata_lock_for_target(content_type: ContentType, object_id: int) -> SeoMetadataLock | None:
    return SeoMetadataLock.objects.filter(content_type=content_type, object_id=object_id).first()


def _apply_metadata_payload(target: Any, payload: dict[str, Any], lock: SeoMetadataLock | None) -> list[str]:
    changed_fields: list[str] = []
    title = _clip(payload.get("meta_title", ""), 70)
    description = _clip(payload.get("meta_description", ""), 170)
    canonical = _normalize_text(payload.get("canonical_url", ""))

    if title and not (lock and lock.lock_title):
        target.meta_title = title
        changed_fields.append("meta_title")
    if description and not (lock and lock.lock_description):
        target.meta_description = description
        changed_fields.append("meta_description")
    if canonical and not (lock and lock.lock_canonical):
        target.canonical_url = canonical
        changed_fields.append("canonical_url")

    if changed_fields:
        target._seo_skip_signal = True
        target.save(update_fields=[*changed_fields, "updated_at"])
        target._seo_skip_signal = False
    return changed_fields


def _persist_interlink_suggestions(adapter: ContentAdapter, suggestions: list[dict[str, Any]]) -> None:
    rows = [
        SeoSuggestion(
            content_type=adapter.content_type,
            object_id=adapter.pk,
            suggestion_type=SeoSuggestion.SuggestionType.INTERLINK,
            payload_json=suggestion,
            confidence=float(suggestion.get("score", 0.0)),
            status=SeoSuggestion.Status.PENDING,
        )
        for suggestion in suggestions
    ]
    if rows:
        SeoSuggestion.objects.bulk_create(rows)
    for suggestion in suggestions:
        target_type = suggestion.get("target_type")
        target_model = Post if target_type == "post" else Page
        target_ct = ContentType.objects.get_for_model(target_model)
        SeoLinkEdge.objects.create(
            source_content_type=adapter.content_type,
            source_object_id=adapter.pk,
            target_content_type=target_ct,
            target_object_id=int(suggestion.get("target_id", 0)),
            anchor_text=suggestion.get("anchor_text", "")[:180],
            source_fragment_hash=hashlib.sha1(
                suggestion.get("anchor_text", "").encode("utf-8")
            ).hexdigest()[:40],
            confidence=float(suggestion.get("score", 0.0)),
            status=SeoLinkEdge.Status.SUGGESTED,
        )


def _apply_interlinks(adapter: ContentAdapter, suggestions: list[dict[str, Any]], settings: SeoEngineSettings) -> int:
    if not settings.apply_interlinks_on_audit:
        return 0
    if adapter.is_published and not settings.auto_update_published_links:
        return 0
    if not suggestions:
        return 0

    instance = _get_instance(adapter.route_type, adapter.pk)
    if not instance:
        return 0
    budget = compute_link_budget(
        total_docs=max(Post.objects.published().count() + Page.objects.published().count(), 1),
        word_count=adapter.word_count,
        min_links=settings.min_links_per_doc,
        whitehat_cap=settings.whitehat_cap_max_links,
    )
    new_markdown, applied_count, applied_suggestions = apply_suggestions_to_markdown(
        instance.body_markdown,
        suggestions,
        max_apply=budget,
    )
    if applied_count == 0 or new_markdown == instance.body_markdown:
        return 0

    instance.body_markdown = new_markdown
    instance._seo_skip_signal = True  # type: ignore[union-attr]
    instance.save()
    instance._seo_skip_signal = False  # type: ignore[union-attr]
    if hasattr(instance, "record_revision"):
        instance.record_revision(note=f"SEO interlink auto-update: {applied_count} links applied")

    anchors = {row["anchor_text"] for row in applied_suggestions}
    SeoSuggestion.objects.filter(
        content_type=adapter.content_type,
        object_id=adapter.pk,
        suggestion_type=SeoSuggestion.SuggestionType.INTERLINK,
        status=SeoSuggestion.Status.PENDING,
        payload_json__anchor_text__in=list(anchors),
    ).update(
        status=SeoSuggestion.Status.APPLIED,
        applied_at=timezone.now(),
    )
    SeoLinkEdge.objects.filter(
        source_content_type=adapter.content_type,
        source_object_id=adapter.pk,
        anchor_text__in=list(anchors),
        status=SeoLinkEdge.Status.SUGGESTED,
    ).update(status=SeoLinkEdge.Status.APPLIED)
    return applied_count


def _apply_interlink_payload(target: Any, payload: dict[str, Any]) -> int:
    suggestion = {
        "anchor_text": payload.get("anchor_text", ""),
        "target_url": payload.get("target_url", ""),
        "score": payload.get("score", 0.0),
    }
    markdown, applied_count, _ = apply_suggestions_to_markdown(
        target.body_markdown or "",
        [suggestion],
        max_apply=1,
    )
    if applied_count == 0:
        return 0
    target.body_markdown = markdown
    target._seo_skip_signal = True
    target.save(update_fields=["body_markdown", "updated_at"])
    target._seo_skip_signal = False
    if hasattr(target, "record_revision"):
        target.record_revision(note="SEO interlink suggestion applied")
    return applied_count


def audit_instance(instance: Any, *, trigger: str = "save", request: Any = None) -> SeoAuditSnapshot | None:
    if not instance or not instance.pk:
        return None
    settings = SeoEngineSettings.get_solo()
    if not settings.enable_checks:
        return None

    adapter = _build_adapter_from_instance(instance)
    metadata = resolve_metadata(adapter, request=request).to_dict()

    results = run_checks(
        adapter,
        metadata,
        min_internal_links=settings.min_links_per_doc,
    )
    counters = _score_from_results(results)
    checksum = _checksum(adapter, metadata, results)

    snapshot = SeoAuditSnapshot.objects.create(
        content_type=adapter.content_type,
        object_id=adapter.pk,
        url=adapter.url,
        route_type=adapter.route_type,
        score=counters["score"],
        critical_count=counters["critical_count"],
        warning_count=counters["warning_count"],
        passed_count=counters["passed_count"],
        failed_count=counters["failed_count"],
        trigger=trigger,
        metadata_json=metadata,
        checksum=checksum,
    )

    issue_rows: list[SeoIssue] = []
    for result in results:
        if result.passed:
            continue
        issue_rows.append(
            SeoIssue(
                snapshot=snapshot,
                check_key=result.key,
                severity=result.severity,
                status=SeoIssue.Status.OPEN,
                message=result.message,
                suggested_fix=result.suggested_fix,
                autofixable=result.autofixable,
                details_json=result.details,
            )
        )
    if issue_rows:
        SeoIssue.objects.bulk_create(issue_rows)

    # Rebuild pending suggestions.
    SeoSuggestion.objects.filter(
        content_type=adapter.content_type,
        object_id=adapter.pk,
        status=SeoSuggestion.Status.PENDING,
    ).delete()
    SeoLinkEdge.objects.filter(
        source_content_type=adapter.content_type,
        source_object_id=adapter.pk,
        status=SeoLinkEdge.Status.SUGGESTED,
    ).delete()

    if any(not row.passed and row.autofixable for row in results):
        _build_metadata_suggestion(adapter, metadata)

    target_pool = _target_pool(adapter)
    budget = compute_link_budget(
        total_docs=max(Post.objects.published().count() + Page.objects.published().count(), 1),
        word_count=adapter.word_count,
        min_links=settings.min_links_per_doc,
        whitehat_cap=settings.whitehat_cap_max_links,
    )
    interlink_suggestions = build_interlink_suggestions(
        adapter,
        target_pool,
        max_links=budget,
        min_score=settings.link_suggestion_min_score,
    )
    _persist_interlink_suggestions(adapter, interlink_suggestions)
    try:
        _apply_interlinks(adapter, interlink_suggestions, settings)
    except Exception:
        # Preserve audit snapshot even if link auto-application fails.
        logger.warning("Auto-interlink application failed for %s pk=%s", adapter.route_type, adapter.pk, exc_info=True)

    return snapshot


def audit_content(content_type: str, object_id: int, *, trigger: str = "manual") -> SeoAuditSnapshot | None:
    instance = _get_instance(content_type, object_id)
    if not instance:
        return None
    return audit_instance(instance, trigger=trigger)


def audit_content_batch(
    content_type: str,
    object_ids: Iterable[Any],
    *,
    trigger: str = "save",
    run_autopilot: bool = True,
) -> dict[str, int]:
    """
    Audit a batch of content ids and optionally run autopilot per object.
    """
    normalized = (content_type or "").strip().lower()
    if normalized not in {"post", "page"}:
        return {"processed": 0, "snapshots": 0, "autopilot_approved": 0}

    processed = 0
    snapshots = 0
    autopilot_approved = 0
    unique_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in object_ids or []:
        try:
            value = int(raw_id)
        except (TypeError, ValueError):
            continue
        if value in seen:
            continue
        seen.add(value)
        unique_ids.append(value)

    for object_id in unique_ids:
        instance = _get_instance(normalized, object_id)
        if not instance:
            continue
        processed += 1
        snapshot = audit_instance(instance, trigger=trigger)
        if snapshot:
            snapshots += 1
        if run_autopilot:
            result = run_autopilot_for_instance(instance)
            autopilot_approved += int(result.get("approved") or 0)

    return {
        "processed": processed,
        "snapshots": snapshots,
        "autopilot_approved": autopilot_approved,
    }


def live_check(content_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    model = Post if content_type == "post" else Page
    ct = ContentType.objects.get_for_model(model)
    title = (payload.get("title") or "").strip()
    meta_title = (payload.get("meta_title") or "").strip()
    meta_description = (payload.get("meta_description") or "").strip()
    body_markdown = payload.get("body_markdown") or ""
    canonical_url = payload.get("canonical_url") or ""
    slug = payload.get("slug") or ""
    summary = payload.get("summary") or ""
    excerpt = payload.get("excerpt") or ""

    adapter = ContentAdapter(
        pk=0,
        model=model,
        content_type=ct,
        route_type=content_type,
        title=title,
        slug=slug,
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        body_markdown=body_markdown,
        body_html="",
        word_count=len((body_markdown or "").split()),
        created_at=timezone.now(),
        updated_at=timezone.now(),
        published_at=None,
        url="/",
        summary=summary,
        excerpt=excerpt,
        og_image_url="",
        is_featured=False,
        status="draft",
    )
    metadata = resolve_metadata(adapter).to_dict()
    settings = SeoEngineSettings.get_solo()
    results = run_checks(adapter, metadata, min_internal_links=settings.min_links_per_doc)
    counters = _score_from_results(results)

    # Group failing checks by related_field for inline OOB rendering
    field_checks: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        serialized = _serialize_check_result(row)
        rf = serialized.get("related_field", "")
        if rf:
            field_checks.setdefault(rf, []).append(serialized)

    return {
        "score": counters["score"],
        "critical_count": counters["critical_count"],
        "warning_count": counters["warning_count"],
        "results": [_serialize_check_result(row) for row in results],
        "field_checks": field_checks,
        "metadata": metadata,
    }


def apply_due_autofixes() -> dict[str, Any]:
    settings = SeoEngineSettings.get_solo()
    if not settings.auto_fix_enabled:
        return {"updated": 0, "reason": "disabled"}
    cutoff = timezone.now() - timedelta(hours=max(settings.auto_fix_after_hours, 1))
    pending_due = SeoSuggestion.objects.filter(
        suggestion_type=SeoSuggestion.SuggestionType.METADATA,
        status__in=[SeoSuggestion.Status.PENDING, SeoSuggestion.Status.NEEDS_CORRECTION],
        created_at__lte=cutoff,
    ).count()
    # Approval-first policy: scheduled tasks only surface due suggestions, never auto-apply.
    return {"updated": 0, "pending_due": pending_due, "reason": "approval_required"}


def run_autopilot_for_instance(
    instance: Any,
    *,
    reviewer: AbstractBaseUser | Any | None = None,
    min_confidence: float | None = None,
    limit: int = 120,
) -> dict[str, Any]:
    """
    Auto-approve safe suggestions for a single content instance.
    """
    if not instance or not getattr(instance, "pk", None):
        return {"ok": False, "reason": "missing_instance", "approved": 0, "skipped": 0}

    settings = SeoEngineSettings.get_solo()
    if not settings.auto_fix_enabled:
        return {"ok": False, "reason": "autopilot_disabled", "approved": 0, "skipped": 0}

    threshold = (
        settings.autopilot_min_confidence if min_confidence is None else float(min_confidence)
    )
    threshold = max(min(threshold, 1.0), 0.0)
    safe_limit = max(int(limit or 0), 1)

    content_type = ContentType.objects.get_for_model(instance.__class__)
    candidates = list(
        SeoSuggestion.objects.filter(
            content_type=content_type,
            object_id=instance.pk,
            status__in=[SeoSuggestion.Status.PENDING, SeoSuggestion.Status.NEEDS_CORRECTION],
            suggestion_type__in=[
                SeoSuggestion.SuggestionType.METADATA,
                SeoSuggestion.SuggestionType.INTERLINK,
            ],
            confidence__gte=threshold,
        )
        .order_by("-confidence", "created_at")[:safe_limit]
    )

    approved = 0
    skipped = 0
    for suggestion in candidates:
        result = approve_suggestion(suggestion.pk, reviewer=reviewer)  # type: ignore[arg-type]
        if result.get("ok"):
            approved += 1
        else:
            skipped += 1

    return {
        "ok": True,
        "approved": approved,
        "skipped": skipped,
        "considered": len(candidates),
        "threshold": threshold,
    }


def handle_deleted_content(instance: Any) -> str | None:
    if not instance:
        return None
    old_path = ""
    try:
        old_path = instance.get_absolute_url()
    except Exception:
        pass
    if not old_path:
        return None
    old_path = old_path if old_path.startswith("/") else f"/{old_path}"

    ct = ContentType.objects.get_for_model(instance.__class__)
    SeoSuggestion.objects.create(
        content_type=ct,
        object_id=getattr(instance, "pk", 0) or 0,
        suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
        payload_json={
            "old_path": old_path,
            "suggested_target": "/",
            "status_code": 301,
        },
        confidence=0.5,
        status=SeoSuggestion.Status.PENDING,
    )
    SeoRedirectRule.objects.get_or_create(
        old_path=old_path,
        defaults={
            "target_url": "",
            "status_code": SeoRedirectRule.StatusCode.GONE,
            "is_active": True,
            "source_model": f"{instance._meta.app_label}.{instance._meta.model_name}",
            "source_object_id": getattr(instance, "pk", None),
            "notes": "Auto-created on content deletion.",
        },
    )
    return old_path


def disable_gone_redirect_for_live_instance(instance: Any) -> int:
    if not instance:
        return 0

    path = ""
    try:
        path = instance.get_absolute_url()
    except Exception:
        return 0

    if not path:
        return 0
    path = path if path.startswith("/") else f"/{path}"

    return SeoRedirectRule.objects.filter(
        old_path=path,
        is_active=True,
        status_code=SeoRedirectRule.StatusCode.GONE,
    ).update(
        is_active=False,
        notes="Auto-disabled because content path is live.",
    )


def approve_suggestion(candidate_id: int, *, reviewer: AbstractBaseUser | Any | None = None) -> dict[str, Any]:
    suggestion = SeoSuggestion.objects.select_related("content_type").filter(pk=candidate_id).first()
    if not suggestion:
        return {"ok": False, "message": "Suggestion not found.", "status": 404}
    if suggestion.status not in {
        SeoSuggestion.Status.PENDING,
        SeoSuggestion.Status.NEEDS_CORRECTION,
    }:
        return {"ok": False, "message": "Suggestion is not approvable.", "status": 409}

    model = suggestion.content_type.model_class()
    target = model.objects.filter(pk=suggestion.object_id).first() if model else None
    payload: dict[str, Any] = cast("dict[str, Any]", suggestion.payload_json or {})  # type: ignore[reportUnknownMemberType]
    now = timezone.now()

    if suggestion.suggestion_type == SeoSuggestion.SuggestionType.METADATA:  # type: ignore[comparison-overlap]
        if not target:
            return {"ok": False, "message": "Target content not found.", "status": 404}
        lock = _metadata_lock_for_target(suggestion.content_type, suggestion.object_id)
        changed = _apply_metadata_payload(target, payload, lock)
        suggestion.status = SeoSuggestion.Status.APPLIED
        suggestion.applied_at = now
        suggestion.save(update_fields=["status", "applied_at"])
        return {
            "ok": True,
            "message": "Metadata suggestion approved.",
            "changed_fields": changed,
            "target_url": target.get_absolute_url(),  # type: ignore[union-attr]
        }

    if suggestion.suggestion_type == SeoSuggestion.SuggestionType.INTERLINK:  # type: ignore[comparison-overlap]
        if not target:
            return {"ok": False, "message": "Target content not found.", "status": 404}
        applied_count = _apply_interlink_payload(target, payload)
        if applied_count == 0:
            return {"ok": False, "message": "Anchor not found in body text.", "status": 409}
        suggestion.status = SeoSuggestion.Status.APPLIED
        suggestion.applied_at = now
        suggestion.save(update_fields=["status", "applied_at"])
        return {
            "ok": True,
            "message": "Interlink suggestion approved.",
            "applied_count": applied_count,
            "target_url": target.get_absolute_url(),  # type: ignore[union-attr]
        }

    if suggestion.suggestion_type == SeoSuggestion.SuggestionType.REDIRECT:  # type: ignore[comparison-overlap]
        old_path: str = payload.get("old_path", "")
        target_url: str = payload.get("suggested_target", "/")
        if not old_path:
            return {"ok": False, "message": "Redirect payload is incomplete.", "status": 409}
        status_code = int(payload.get("status_code", 301))
        if status_code not in {301, 302, 410}:
            status_code = 301
        rule, _ = SeoRedirectRule.objects.update_or_create(
            old_path=old_path,
            defaults={
                "target_url": target_url if status_code != 410 else "",
                "status_code": status_code,
                "is_active": True,
                "notes": "Approved from SEO suggestion queue.",
                "created_by": reviewer if getattr(reviewer, "is_authenticated", False) else None,
            },
        )
        suggestion.status = SeoSuggestion.Status.APPLIED
        suggestion.applied_at = now
        suggestion.save(update_fields=["status", "applied_at"])
        return {
            "ok": True,
            "message": "Redirect suggestion approved.",
            "redirect_rule_id": rule.pk,
        }

    return {"ok": False, "message": "Unsupported suggestion type.", "status": 409}


def reject_suggestion(candidate_id: int) -> dict[str, Any]:
    suggestion = SeoSuggestion.objects.filter(pk=candidate_id).first()
    if not suggestion:
        return {"ok": False, "message": "Suggestion not found.", "status": 404}
    if suggestion.status not in {
        SeoSuggestion.Status.PENDING,
        SeoSuggestion.Status.NEEDS_CORRECTION,
    }:
        return {"ok": False, "message": "Suggestion is not rejectable.", "status": 409}
    suggestion.status = SeoSuggestion.Status.REJECTED
    suggestion.save(update_fields=["status"])
    return {"ok": True, "message": "Suggestion rejected."}


def seo_overview_metrics() -> dict[str, Any]:
    latest_snapshot = SeoAuditSnapshot.objects.order_by("-audited_at").first()
    issue_counts = {
        "critical_open": SeoIssue.objects.filter(
            status=SeoIssue.Status.OPEN,
            severity=SeoIssue.Severity.CRITICAL,
        ).count(),
        "warning_open": SeoIssue.objects.filter(
            status=SeoIssue.Status.OPEN,
            severity=SeoIssue.Severity.WARNING,
        ).count(),
    }
    suggestion_counts = {
        "pending_total": SeoSuggestion.objects.filter(status=SeoSuggestion.Status.PENDING).count(),
        "pending_metadata": SeoSuggestion.objects.filter(
            status=SeoSuggestion.Status.PENDING,
            suggestion_type=SeoSuggestion.SuggestionType.METADATA,
        ).count(),
        "pending_interlinks": SeoSuggestion.objects.filter(
            status=SeoSuggestion.Status.PENDING,
            suggestion_type=SeoSuggestion.SuggestionType.INTERLINK,
        ).count(),
        "pending_redirects": SeoSuggestion.objects.filter(
            status=SeoSuggestion.Status.PENDING,
            suggestion_type=SeoSuggestion.SuggestionType.REDIRECT,
        ).count(),
    }
    route_breakdown = list(
        SeoAuditSnapshot.objects.values("route_type")
        .annotate(total=Count("id"), avg_score=Avg("score"))
        .order_by("route_type")
    )
    return {
        "latest_score": latest_snapshot.score if latest_snapshot else None,
        "latest_audited_at": latest_snapshot.audited_at if latest_snapshot else None,
        "issue_counts": issue_counts,
        "suggestion_counts": suggestion_counts,
        "route_breakdown": route_breakdown,
    }
