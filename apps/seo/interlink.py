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
    Suggest internal links for a post based on content matching.
    
    Args:
        post: Post instance
        max_suggestions: Maximum number of suggestions to return
    
    Returns:
        List of dicts with 'anchor_text', 'target_url', 'target_type', 'target_id', 'score'
    """
    from blog.models import Post as PostModel
    from pages.models import Page as PageModel

    if not post or not post.pk:
        return []

    # Fetch source pool once to avoid duplicated queries and stale counts.
    other_posts = list(
        PostModel.objects.published()
        .exclude(pk=post.pk)
        .order_by("-published_at")[:50]
    )

    pages = list(PageModel.objects.published().order_by("-published_at")[:20])

    # Build adapter-like objects for compatibility
    target_adapters = [
        SimpleNamespace(
            route_type="post",
            pk=p.pk,
            title=p.title,
            url=p.get_absolute_url(),
            excerpt_or_summary=p.excerpt or "",
            is_featured=p.is_featured,
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
        )
        for p in pages
    )

    # Build source adapter
    source_adapter = SimpleNamespace(
        route_type="post",
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
