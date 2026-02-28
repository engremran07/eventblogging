from __future__ import annotations

import re

from django.utils import timezone

from blog.services import build_embedding_vector, cosine_similarity

from .models import Page

TOKEN_RE = re.compile(r"[a-zA-Z0-9]{2,}")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


def _tokenize_text(text: str):
    if not text:
        return set()
    return {
        match.group(0).lower()
        for match in TOKEN_RE.finditer(text)
        if match.group(0).lower() not in STOP_WORDS
    }


def _page_document(page):
    return " ".join(
        part
        for part in [
            page.title,
            page.summary,
            page.nav_label,
            page.template_key,
            (page.body_markdown or "")[:2000],
        ]
        if part
    )


def _template_score(anchor_page, candidate_page):
    if not anchor_page:
        return 0.0
    return 1.0 if anchor_page.template_key == candidate_page.template_key else 0.0


def _navigation_score(anchor_page, candidate_page):
    if not anchor_page:
        return 1.0 if candidate_page.show_in_navigation else 0.0
    if anchor_page.show_in_navigation and candidate_page.show_in_navigation:
        return 1.0
    if anchor_page.show_in_navigation != candidate_page.show_in_navigation:
        return 0.4
    return 0.7


def _freshness_score(page):
    if not page.updated_at:
        return 0.0
    age_days = max((timezone.now() - page.updated_at).days, 0)
    return max(0.0, 1.0 - (min(age_days, 365) / 365.0))


def get_related_pages_algorithmic(
    user,
    query_text: str = "",
    limit: int = 4,
    anchor_page: Page | None = None,
    with_explanations: bool = False,
):
    candidates = list(
        Page.objects.visible_to(user)
        .select_related("author")
        .order_by("-published_at", "-updated_at", "-created_at")[:160]
    )
    if not candidates:
        return []

    seed_text = (query_text or "").strip()
    anchor_id = anchor_page.pk if anchor_page else None

    if not seed_text:
        if anchor_page:
            seed_text = _page_document(anchor_page)
        else:
            anchor_page = candidates[0]
            anchor_id = anchor_page.id
            seed_text = _page_document(anchor_page)

    seed_vector = build_embedding_vector(seed_text)
    seed_tokens = _tokenize_text(seed_text)

    ranked = []
    for page in candidates:
        if anchor_id and page.id == anchor_id:
            continue

        page_document = _page_document(page)
        page_vector = build_embedding_vector(page_document)
        semantic_raw = cosine_similarity(seed_vector, page_vector)
        semantic_score = max(min((semantic_raw + 1.0) / 2.0, 1.0), 0.0)

        page_tokens = _tokenize_text(page_document)
        lexical_union = seed_tokens | page_tokens
        lexical_score = (len(seed_tokens & page_tokens) / len(lexical_union)) if lexical_union else 0.0

        template_score = _template_score(anchor_page, page)
        navigation_score = _navigation_score(anchor_page, page)
        freshness_score = _freshness_score(page)
        editorial_score = 1.0 if page.is_featured else 0.0

        total_score = (
            (0.47 * semantic_score)
            + (0.20 * lexical_score)
            + (0.13 * template_score)
            + (0.10 * navigation_score)
            + (0.05 * freshness_score)
            + (0.05 * editorial_score)
        )

        ranked.append(
            {
                "page": page,
                "total_score": total_score,
                "components": {
                    "semantic": round(semantic_score, 5),
                    "lexical": round(lexical_score, 5),
                    "template": round(template_score, 5),
                    "navigation": round(navigation_score, 5),
                    "freshness": round(freshness_score, 5),
                    "editorial": round(editorial_score, 5),
                },
            }
        )

    ranked.sort(
        key=lambda item: (
            item["total_score"],
            item["page"].updated_at or item["page"].created_at,
        ),
        reverse=True,
    )
    top_ranked = ranked[:limit]
    if with_explanations:
        return top_ranked
    return [item["page"] for item in top_ranked]
