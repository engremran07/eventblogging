from __future__ import annotations

import math
import re
from collections import Counter
from types import SimpleNamespace
from typing import Any

from .models import TaxonomySynonymGroup
from .synonyms import expand_terms

PHRASE_TOKEN_RE = re.compile(r"[a-zA-Z0-9]{3,}")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)
SENTENCE_RE = re.compile(r"[^\n.!?]{20,}")

STOP_WORDS = {
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "have",
    "about",
    "should",
    "would",
    "there",
    "while",
}


def _tokens(text: str) -> list[str]:
    if not text:
        return []
    return [
        token.lower()
        for token in PHRASE_TOKEN_RE.findall(text)
        if token.lower() not in STOP_WORDS
    ]


def compute_link_budget(total_docs: int, *, word_count: int, min_links: int, whitehat_cap: int) -> int:
    branching_target = max(math.ceil(max(total_docs, 1) ** (1 / 3)), min_links)
    length_bonus = max(min(word_count // 1200, 2), 0)
    raw_target = max(min_links, branching_target + length_bonus)
    return max(min(raw_target, whitehat_cap), min_links)


def _extract_anchor_candidates(body_markdown: str) -> list[str]:
    headings = [match.group(1).strip() for match in HEADING_RE.finditer(body_markdown or "")]
    sentences = [segment.strip() for segment in SENTENCE_RE.findall(body_markdown or "")]

    phrase_counter: Counter[str] = Counter()
    for source_text in headings + sentences:
        tokens = _tokens(source_text)
        if len(tokens) < 2:
            continue
        max_window = 4 if len(tokens) > 4 else len(tokens)
        for window in range(2, max_window + 1):
            for idx in range(0, len(tokens) - window + 1):
                phrase = " ".join(tokens[idx : idx + window]).strip()
                if not phrase:
                    continue
                phrase_counter[phrase] += 1

    ranked: list[tuple[float, str]] = []
    for phrase, count in phrase_counter.items():
        if len(phrase) < 8:
            continue
        ranked.append((count + min(len(phrase.split()) * 0.2, 0.6), phrase))
    ranked.sort(reverse=True)
    return [phrase for _, phrase in ranked[:200]]


def _target_score(anchor_text: str, target: Any) -> float:
    anchor_tokens = expand_terms(_tokens(anchor_text), scope=TaxonomySynonymGroup.Scope.ALL)
    if not anchor_tokens:
        return 0.0
    target_tokens = expand_terms(
        _tokens(" ".join([target.title or "", target.excerpt_or_summary or ""])),
        scope=TaxonomySynonymGroup.Scope.ALL,
    )
    if not target_tokens:
        return 0.0
    overlap = len(anchor_tokens & target_tokens)
    union = len(anchor_tokens | target_tokens) or 1
    base = overlap / union

    # TF-IDF boost: if target has tfidf_vector, score overlap with anchor terms
    tfidf_vector = getattr(target, "tfidf_vector", None) or {}
    if tfidf_vector and isinstance(tfidf_vector, dict):
        tfidf_boost = sum(
            tfidf_vector.get(tok, 0.0) for tok in anchor_tokens
        )
        base += min(tfidf_boost * 0.3, 0.15)  # Cap TF-IDF boost at 0.15

    if target.is_featured:
        base += 0.05
    return min(base, 1.0)


def build_interlink_suggestions(source_adapter: Any, target_adapters: Any, *, max_links: int, min_score: float = 0.1) -> list[dict[str, Any]]:
    body_text = source_adapter.body_markdown or ""
    anchor_candidates = _extract_anchor_candidates(body_text)
    if not anchor_candidates:
        return []

    used_target_ids: set[tuple[str, object]] = set()
    used_anchors: set[str] = set()
    suggestions: list[dict[str, Any]] = []

    for anchor in anchor_candidates:
        best_target = None
        best_score = 0.0
        for target in target_adapters:
            target_key = (target.route_type, target.pk)
            if target_key in used_target_ids:
                continue
            score = _target_score(anchor, target)
            if score > best_score:
                best_score = score
                best_target = target

        if not best_target or best_score < min_score:
            continue
        if anchor in used_anchors:
            continue
        if anchor not in body_text.lower():
            continue

        suggestions.append(
            {
                "anchor_text": anchor,
                "target_url": best_target.url,
                "target_type": best_target.route_type,
                "target_id": best_target.pk,
                "score": round(best_score, 4),
            }
        )
        used_target_ids.add((best_target.route_type, best_target.pk))
        used_anchors.add(anchor)
        if len(suggestions) >= max_links:
            break

    return suggestions


def apply_suggestions_to_markdown(body_markdown: str, suggestions: list[dict[str, Any]], *, max_apply: int) -> tuple[str, int, list[dict[str, Any]]]:
    content = body_markdown or ""
    applied = 0
    applied_suggestions: list[dict[str, Any]] = []

    for suggestion in suggestions:
        if applied >= max_apply:
            break
        anchor = suggestion.get("anchor_text", "").strip()
        target_url = suggestion.get("target_url", "").strip()
        if not anchor or not target_url:
            continue
        if f"[{anchor}](" in content:
            continue

        # Replace first standalone occurrence of anchor text with markdown link.
        pattern = re.compile(rf"(?<!\[)\b{re.escape(anchor)}\b(?!\])", re.IGNORECASE)
        content, changes = pattern.subn(f"[{anchor}]({target_url})", content, count=1)
        if changes:
            applied += 1
            applied_suggestions.append(suggestion)

    return content, applied, applied_suggestions


def suggest_internal_links(post: Any, *, max_suggestions: int = 8) -> list[dict[str, Any]]:
    """
    Suggest internal links for a post/page based on content matching.
    Uses the FULL published content pool (no artificial caps) to maximize
    crawl-budget coverage — every piece of content is a potential target.

    Args:
        post: Post or Page instance
        max_suggestions: Maximum number of suggestions to return

    Returns:
        List of dicts with 'anchor_text', 'target_url', 'target_type', 'target_id', 'score'
    """
    from blog.models import Post as PostModel
    from pages.models import Page as PageModel

    if not post or not post.pk:
        return []

    is_post = isinstance(post, PostModel)
    is_page = isinstance(post, PageModel)

    # Fetch FULL published content pool — no recency caps
    other_posts = list(
        PostModel.objects.published()
        .exclude(pk=post.pk if is_post else -1)
        .only(
            "id", "title", "excerpt", "slug", "body_markdown", "body_html",
            "word_count", "published_at", "updated_at", "created_at",
            "status", "is_featured", "tfidf_vector",
        )
    )

    pages = list(
        PageModel.objects.published()
        .exclude(pk=post.pk if is_page else -1)
        .only(
            "id", "title", "summary", "slug", "body_markdown", "body_html",
            "word_count", "published_at", "updated_at", "created_at",
            "status", "is_featured", "tfidf_vector",
        )
    )

    # Build adapter-like objects for compatibility
    target_adapters = [
        SimpleNamespace(
            route_type="post",
            pk=p.pk,
            title=p.title,
            url=p.get_absolute_url(),
            excerpt_or_summary=p.excerpt or "",
            is_featured=p.is_featured,
            tfidf_vector=getattr(p, "tfidf_vector", {}) or {},
        )
        for p in other_posts
    ]

    target_adapters.extend(
        SimpleNamespace(
            route_type="page",
            pk=p.pk,
            title=p.title,
            url=p.get_absolute_url(),
            excerpt_or_summary=p.summary or "",
            is_featured=False,
            tfidf_vector=getattr(p, "tfidf_vector", {}) or {},
        )
        for p in pages
    )

    # Build source adapter
    source_adapter = SimpleNamespace(
        route_type="post" if is_post else "page",
        body_markdown=post.body_markdown,
        pk=post.pk,
    )

    # Get engine settings for min score and max links
    from .models import SeoEngineSettings

    engine_settings = SeoEngineSettings.get_solo()
    min_score = engine_settings.link_suggestion_min_score
    max_links = compute_link_budget(
        total_docs=len(other_posts) + len(pages),
        word_count=len((post.body_markdown or "").split()),
        min_links=2,
        whitehat_cap=engine_settings.whitehat_cap_max_links,
    )

    # Build suggestions
    suggestions = build_interlink_suggestions(
        source_adapter,
        target_adapters,
        max_links=min(max_links, max_suggestions),
        min_score=min_score,
    )

    return suggestions


# ---------------------------------------------------------------------------
# Reverse linking — When A links to B, suggest B link back to A
# ---------------------------------------------------------------------------

def reverse_interlink_scan(source_instance: Any) -> list[dict[str, Any]]:
    """
    For a newly saved piece of content, find all published content that
    already links TO it and create reverse-link suggestions FROM those
    pieces BACK to this content — ensuring bidirectional crawl paths.
    """
    import logging

    from django.contrib.contenttypes.models import ContentType

    from .models import SeoLinkEdge

    logger = logging.getLogger(__name__)

    if not source_instance or not source_instance.pk:
        return []

    ct = ContentType.objects.get_for_model(source_instance.__class__)

    inbound_edges = list(
        SeoLinkEdge.objects.filter(
            target_content_type=ct,
            target_object_id=source_instance.pk,
            status=SeoLinkEdge.Status.APPLIED,
        )
        .select_related("source_content_type")
        .only("source_content_type", "source_object_id", "anchor_text")
    )

    if not inbound_edges:
        return []

    reverse_suggestions: list[dict[str, Any]] = []
    source_url = source_instance.get_absolute_url()
    source_title = getattr(source_instance, "title", "") or ""

    for edge in inbound_edges:
        existing = SeoLinkEdge.objects.filter(
            source_content_type=ct,
            source_object_id=source_instance.pk,
            target_content_type=edge.source_content_type,
            target_object_id=edge.source_object_id,
        ).exists()

        if existing:
            continue

        linker_model = edge.source_content_type.model_class()
        if not linker_model:
            continue
        linker = linker_model.objects.filter(pk=edge.source_object_id).first()
        if not linker:
            continue

        linker_title = getattr(linker, "title", "") or ""
        anchor = source_title[:60] if source_title else f"Related: {linker_title[:40]}"

        reverse_suggestions.append({
            "anchor_text": anchor,
            "target_url": source_url,
            "target_type": "post" if hasattr(source_instance, "excerpt") else "page",
            "target_id": source_instance.pk,
            "source_id": linker.pk,
            "source_type": edge.source_content_type.model,
            "score": 0.6,
        })

    logger.debug(
        "Reverse interlink scan for %s pk=%s: %d suggestions",
        ct.model, source_instance.pk, len(reverse_suggestions),
    )
    return reverse_suggestions


# ---------------------------------------------------------------------------
# Orphan detection & repair
# ---------------------------------------------------------------------------

def find_orphan_content() -> dict[str, list[int]]:
    """Find all published content with zero inbound links (orphans)."""
    from django.contrib.contenttypes.models import ContentType

    from blog.models import Post as PostModel
    from pages.models import Page as PageModel

    from .models import SeoLinkEdge

    post_ct = ContentType.objects.get_for_model(PostModel)
    page_ct = ContentType.objects.get_for_model(PageModel)

    linked_post_ids = set(
        SeoLinkEdge.objects.filter(
            target_content_type=post_ct,
            status=SeoLinkEdge.Status.APPLIED,
        ).values_list("target_object_id", flat=True)
    )
    orphan_posts = [
        p.pk for p in PostModel.objects.published().only("id")
        if p.pk not in linked_post_ids
    ]

    linked_page_ids = set(
        SeoLinkEdge.objects.filter(
            target_content_type=page_ct,
            status=SeoLinkEdge.Status.APPLIED,
        ).values_list("target_object_id", flat=True)
    )
    orphan_pages = [
        p.pk for p in PageModel.objects.published().only("id")
        if p.pk not in linked_page_ids
    ]

    return {"posts": orphan_posts, "pages": orphan_pages}


def repair_orphans(*, max_repairs: int = 50) -> dict[str, int]:
    """
    Orphan Safety Net — For each orphan, find the best existing content
    to link FROM and create a suggestion. Ensures every published piece
    of content is reachable in a single crawl.
    """
    import logging

    from blog.models import Post as PostModel
    from pages.models import Page as PageModel

    logger = logging.getLogger(__name__)

    orphans = find_orphan_content()
    repairs_created = 0

    all_posts = list(PostModel.objects.published().only(
        "id", "title", "body_markdown", "tfidf_vector", "is_featured",
    ))
    all_pages = list(PageModel.objects.published().only(
        "id", "title", "body_markdown", "tfidf_vector", "is_featured",
    ))

    all_content: list[tuple[str, Any]] = [
        ("post", p) for p in all_posts
    ] + [
        ("page", p) for p in all_pages
    ]

    for post_pk in orphans.get("posts", [])[:max_repairs]:
        orphan = PostModel.objects.filter(pk=post_pk).first()
        if not orphan:
            continue
        best_source = _find_best_linker(orphan, all_content)
        if best_source:
            suggestions = suggest_internal_links(best_source[1], max_suggestions=1)
            if suggestions:
                repairs_created += 1

    for page_pk in orphans.get("pages", [])[:max_repairs]:
        orphan = PageModel.objects.filter(pk=page_pk).first()
        if not orphan:
            continue
        best_source = _find_best_linker(orphan, all_content)
        if best_source:
            repairs_created += 1

    logger.info(
        "Orphan repair: %d orphan posts, %d orphan pages, %d repairs created",
        len(orphans.get("posts", [])),
        len(orphans.get("pages", [])),
        repairs_created,
    )
    return {
        "orphan_posts": len(orphans.get("posts", [])),
        "orphan_pages": len(orphans.get("pages", [])),
        "repairs_created": repairs_created,
    }


def _find_best_linker(
    orphan: Any,
    all_content: list[tuple[str, Any]],
) -> tuple[str, Any] | None:
    """Find the best existing content to link FROM to the orphan."""
    orphan_title = getattr(orphan, "title", "") or ""
    orphan_tokens = set(_tokens(orphan_title))
    if not orphan_tokens:
        return None

    best_score = 0.0
    best_source: tuple[str, Any] | None = None

    for content_type, content in all_content:
        if content.pk == orphan.pk:
            continue
        source_title = getattr(content, "title", "") or ""
        source_tokens = set(_tokens(source_title))
        if not source_tokens:
            continue
        overlap = len(orphan_tokens & source_tokens)
        union = len(orphan_tokens | source_tokens) or 1
        score = overlap / union
        if score > best_score:
            best_score = score
            best_source = (content_type, content)

    return best_source if best_score > 0.05 else None


def verify_graph_connectivity() -> dict[str, Any]:
    """
    Verify that the internal link graph is fully connected.
    Returns graph connectivity statistics.
    """
    from blog.models import Post as PostModel
    from pages.models import Page as PageModel

    from .models import SeoLinkEdge

    nodes: set[str] = set()
    edges_graph: dict[str, set[str]] = {}

    for post in PostModel.objects.published().only("id"):
        node_id = f"post:{post.pk}"
        nodes.add(node_id)
        edges_graph.setdefault(node_id, set())

    for page in PageModel.objects.published().only("id"):
        node_id = f"page:{page.pk}"
        nodes.add(node_id)
        edges_graph.setdefault(node_id, set())

    for edge in SeoLinkEdge.objects.filter(status=SeoLinkEdge.Status.APPLIED).select_related(
        "source_content_type", "target_content_type"
    ):
        source_type = edge.source_content_type.model
        target_type = edge.target_content_type.model
        source_id = f"{source_type}:{edge.source_object_id}"
        target_id = f"{target_type}:{edge.target_object_id}"
        if source_id in nodes and target_id in nodes:
            edges_graph.setdefault(source_id, set()).add(target_id)

    total_nodes = len(nodes)
    if total_nodes == 0:
        return {"total_nodes": 0, "reachable": 0, "orphans": 0, "connected": True}

    start = next(iter(nodes))
    visited: set[str] = set()
    queue = [start]
    visited.add(start)

    while queue:
        current = queue.pop(0)
        for neighbor in edges_graph.get(current, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    orphan_nodes = nodes - visited
    return {
        "total_nodes": total_nodes,
        "reachable": len(visited),
        "orphans": len(orphan_nodes),
        "orphan_ids": sorted(orphan_nodes)[:50],
        "connected": len(visited) == total_nodes,
    }
