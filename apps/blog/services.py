from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from datetime import datetime

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone

from comments.models import NewsletterSubscriber, PostBookmark, PostLike
from seo.models import TaxonomySynonymGroup
from seo.synonyms import augment_weighted_terms, expand_terms

from .forms import PostFilterForm
from .models import Post

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[a-zA-Z0-9]{2,}")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)
EMBEDDING_DIMENSIONS = 192
VECTOR_CACHE_TIMEOUT_SECONDS = 60 * 60 * 12
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
    "you",
    "your",
}

AUTO_TAG_RULES = {
    "django": {"django", "orm", "migration", "middleware"},
    "python": {"python", "typing", "pip", "pytest"},
    "htmx": {"htmx", "hx-get", "hx-post", "partial"},
    "alpinejs": {"alpine", "alpinejs", "x-data"},
    "bootstrap": {"bootstrap", "navbar", "modal"},
    "postgres": {"postgres", "postgresql", "query", "index"},
    "seo": {"seo", "meta", "canonical", "sitemap", "schema"},
    "api-design": {"api", "rest", "json", "endpoint"},
    "performance": {"cache", "latency", "optimization", "performance"},
    "testing": {"test", "tests", "qa", "assert"},
    "security": {"security", "csrf", "xss", "auth"},
}

AUTO_CATEGORY_RULES = {
    "technology/django": {"django", "orm", "migration", "admin"},
    "technology/frontend/htmx": {"htmx", "hx-get", "hx-post"},
    "technology/frontend/alpine": {"alpine", "x-data"},
    "technology/frontend/design-systems": {"bootstrap", "css", "design"},
    "technology/backend/apis": {"api", "endpoint", "json", "rest"},
    "technology/backend/apis/graphql": {"graphql", "schema", "resolver"},
    "writing/tutorial": {"tutorial", "guide", "step", "beginner"},
    "writing/deep-dive": {"deep", "architecture", "internals"},
    "operations/devops/observability": {"observability", "metrics", "logs"},
}

AUTO_TOPIC_RULES = {
    "technology": {"django", "python", "htmx", "alpine", "bootstrap"},
    "engineering": {"architecture", "system", "design", "pattern"},
    "data": {"query", "database", "analytics", "metrics"},
    "security": {"security", "csrf", "xss", "auth"},
    "devops": {"deploy", "observability", "infra", "pipeline"},
    "product": {"roadmap", "product", "workflow", "editorial"},
}


def _tokenize_text(text: str):
    if not text:
        return []
    tokens = [match.group(0).lower() for match in TOKEN_RE.finditer(text)]
    return [token for token in tokens if token not in STOP_WORDS]


def _hash_to_index(token: str, dimensions: int):
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    idx = int.from_bytes(digest[:4], "little") % dimensions
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return idx, sign


def build_embedding_vector(text: str, dimensions: int = EMBEDDING_DIMENSIONS):
    vector = [0.0] * dimensions
    tokens = _tokenize_text(text)

    if not tokens:
        return vector

    for token in tokens:
        weight = 1.2 if len(token) >= 7 else 1.0

        idx, sign = _hash_to_index(token, dimensions)
        vector[idx] += sign * weight

        if len(token) >= 5:
            for i in range(0, len(token) - 2, 2):
                trigram = token[i : i + 3]
                idx, sign = _hash_to_index(trigram, dimensions)
                vector[idx] += sign * (weight * 0.45)

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector

    return [value / norm for value in vector]


def cosine_similarity(vec_a, vec_b):
    return sum(a * b for a, b in zip(vec_a, vec_b, strict=False))


def _post_document(post):
    tag_names = " ".join(tag.name for tag in post.tags.all())
    category_names = " ".join(category.name for category in post.categories.all())
    topic_name = getattr(post.primary_topic, "name", "") if post.primary_topic else ""

    return " ".join(
        part
        for part in [
            post.title,
            post.subtitle,
            post.excerpt,
            topic_name,
            tag_names,
            category_names,
            (post.body_markdown or "")[:1400],
        ]
        if part
    )


def _post_vector_signature(post):
    tags = "|".join(sorted(tag.name for tag in post.tags.all()))
    categories = "|".join(sorted(category.name for category in post.categories.all()))
    topic = getattr(post.primary_topic, "name", "") if post.primary_topic else ""
    updated = ""
    if post.updated_at:
        updated = str(int(post.updated_at.timestamp()))
    digest = hashlib.blake2s(
        f"{post.pk}:{updated}:{topic}:{tags}:{categories}".encode(),
        digest_size=8,
    ).hexdigest()
    return digest


def _post_vector_cache_key(post):
    return f"blog:post-vector:v2:{post.pk}:{_post_vector_signature(post)}"


def _get_post_vector(post):
    cache_key = _post_vector_cache_key(post)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    vector = build_embedding_vector(_post_document(post))
    cache.set(cache_key, vector, VECTOR_CACHE_TIMEOUT_SECONDS)
    return vector


def warm_post_vector_cache(post):
    if not post or not post.pk:
        return
    _get_post_vector(post)


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _taxonomy_sets_for_post(post):
    return {
        "tags": {tag.name for tag in post.tags.all()},
        "categories": {category.name for category in post.categories.all()},
        "topic": {post.primary_topic.name} if post.primary_topic else set(),
    }


def _taxonomy_overlap(anchor_taxonomy, candidate_taxonomy):
    if not anchor_taxonomy:
        return 0.0
    tag_overlap = _jaccard_similarity(anchor_taxonomy["tags"], candidate_taxonomy["tags"])
    category_overlap = _jaccard_similarity(
        anchor_taxonomy["categories"],
        candidate_taxonomy["categories"],
    )
    topic_overlap = _jaccard_similarity(anchor_taxonomy["topic"], candidate_taxonomy["topic"])
    return (0.5 * tag_overlap) + (0.35 * category_overlap) + (0.15 * topic_overlap)


def _lexical_rank_map(post_ids, seed_text: str):
    seed_text = (seed_text or "").strip()
    if not post_ids or not seed_text:
        return {}
    try:
        query = SearchQuery(seed_text, search_type="plain")
        rows = list(
            Post.objects.filter(pk__in=post_ids)
            .annotate(
                search_document=(
                    SearchVector("title", weight="A")
                    + SearchVector("excerpt", weight="A")
                    + SearchVector("subtitle", weight="B")
                    + SearchVector("body_markdown", weight="C")
                )
            )
            .annotate(search_rank=SearchRank("search_document", query))
            .values_list("pk", "search_rank")
        )
        if not rows:
            return {}
        max_rank = max(float(rank or 0.0) for _, rank in rows) or 1.0
        return {post_id: min(max(float(rank or 0.0) / max_rank, 0.0), 1.0) for post_id, rank in rows}
    except Exception:
        logger.warning("FTS rank scoring failed; returning empty ranking map", exc_info=True)
        return {}


def _recommendation_type(post: Post, taxonomy_score: float, semantic_score: float) -> str:
    if post.reading_time >= 8:
        return "deep_dive"
    if taxonomy_score < 0.18 and semantic_score >= 0.62:
        return "alternative"
    return "beginner"


def get_related_posts_algorithmic(
    user: object,
    query_text: str = "",
    limit: int = 5,
    anchor_post: Post | None = None,
    with_explanations: bool = False,
) -> list[Post] | list[dict[str, object]]:
    candidates = list(
        Post.objects.visible_to(user)
        .select_related("author", "primary_topic")
        .prefetch_related("tags", "categories")
        .order_by("-published_at", "-created_at")[:180]
    )

    if not candidates:
        return []

    seed_text = (query_text or "").strip()
    anchor_id = anchor_post.pk if anchor_post else None

    if not seed_text:
        if anchor_post:
            seed_text = _post_document(anchor_post)
        else:
            anchor_post = candidates[0]
            anchor_id = anchor_post.id
            seed_text = _post_document(anchor_post)

    seed_vector = (
        _get_post_vector(anchor_post) if anchor_post and not query_text.strip() else build_embedding_vector(seed_text)
    )
    anchor_taxonomy = _taxonomy_sets_for_post(anchor_post) if anchor_post else None

    candidate_ids = [post.id for post in candidates if post.id != anchor_id]
    lexical_ranks = _lexical_rank_map(candidate_ids, seed_text)
    max_views = max(post.views_count for post in candidates) or 1
    now = timezone.now()

    ranked = []
    for post in candidates:
        if anchor_id and post.id == anchor_id:
            continue

        candidate_vector = _get_post_vector(post)
        semantic_raw = cosine_similarity(seed_vector, candidate_vector)
        semantic_score = max(min((semantic_raw + 1.0) / 2.0, 1.0), 0.0)
        lexical_score = lexical_ranks.get(post.id, 0.0)
        taxonomy_score = _taxonomy_overlap(anchor_taxonomy, _taxonomy_sets_for_post(post))
        behavior_score = min((post.views_count / max_views), 1.0)

        if post.published_at:
            age_days = max((now - post.published_at).days, 0)
        else:
            age_days = 365
        freshness_score = max(0.0, 1.0 - (min(age_days, 365) / 365.0))
        editorial_score = 1.0 if post.is_editors_pick else (0.5 if post.is_featured else 0.0)

        total_score = (
            (0.45 * semantic_score)
            + (0.20 * lexical_score)
            + (0.15 * taxonomy_score)
            + (0.10 * behavior_score)
            + (0.05 * freshness_score)
            + (0.05 * editorial_score)
        )

        recommendation_type = _recommendation_type(post, taxonomy_score, semantic_score)

        ranked.append(
            {
                "post": post,
                "total_score": total_score,
                "recommendation_type": recommendation_type,
                "components": {
                    "semantic": round(semantic_score, 5),
                    "lexical": round(lexical_score, 5),
                    "taxonomy": round(taxonomy_score, 5),
                    "behavior": round(behavior_score, 5),
                    "freshness": round(freshness_score, 5),
                    "editorial": round(editorial_score, 5),
                },
                "explain": (
                    f"semantic={semantic_score:.3f}, lexical={lexical_score:.3f}, "
                    f"taxonomy={taxonomy_score:.3f}, behavior={behavior_score:.3f}, "
                    f"freshness={freshness_score:.3f}"
                ),
            }
        )

    ranked.sort(
        key=lambda item: (
            item["total_score"],
            item["post"].published_at or item["post"].created_at,
        ),
        reverse=True,
    )

    top_ranked = ranked[:limit]
    if with_explanations:
        return top_ranked
    return [item["post"] for item in top_ranked]


def _get_auto_tagging_settings():
    defaults = {
        "enabled": True,
        "max_tags": 6,
        "max_total_tags": 12,
        "max_categories": 3,
        "min_score": 1.2,
    }
    try:
        from core.models import FeatureControlSettings

        controls = FeatureControlSettings.get_solo()
        min_score = float(controls.auto_tagging_min_score)
        max_total_tags = int(getattr(controls, "auto_tagging_max_total_tags", 12))
        defaults.update(
            {
                "enabled": bool(controls.enable_auto_tagging),
                "max_tags": max(int(controls.auto_tagging_max_tags), 1),
                "max_total_tags": max(min(max_total_tags, 25), 1),
                "max_categories": max(int(controls.auto_tagging_max_categories), 1),
                "min_score": max(min_score, 0.0),
            }
        )
    except Exception:
        logger.warning("Failed to load FeatureControlSettings for taxonomy; using defaults", exc_info=True)
    return defaults


def _extract_heading_text(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    headings = [match.group(1).strip() for match in HEADING_RE.finditer(markdown_text)]
    return " ".join(heading for heading in headings if heading)


def _apply_text_weights(weighted, text: str, factor: float):
    if not text:
        return
    for token in _tokenize_text(text):
        weighted[token] += factor


def _weighted_token_profile(post):
    weighted = Counter()

    title = post.title or ""
    excerpt = post.excerpt or ""
    body = post.body_markdown or ""
    headings = _extract_heading_text(body)

    # Prioritize metadata and heading context over long-tail body tokens.
    _apply_text_weights(weighted, title, 3.0)
    _apply_text_weights(weighted, excerpt, 1.8)
    _apply_text_weights(weighted, headings, 2.0)

    # Full-body analysis with normalized frequency to avoid noise from raw dumps.
    body_tokens = _tokenize_text(body)
    if body_tokens:
        body_total = max(len(body_tokens), 1)
        for token, count in Counter(body_tokens).items():
            tf = count / body_total
            weighted[token] += 0.45 + (math.log1p(count) * 0.55) + (tf * 8.0)

    return weighted


def _collect_candidate_terms(tag_model, fallback_terms, limit=260):
    terms = []
    try:
        terms.extend(list(tag_model.objects.order_by("-count", "name").values_list("name", flat=True)[:limit]))
    except Exception:
        logger.warning("Could not query tag model %r for candidate terms", tag_model, exc_info=True)
    for term in fallback_terms:
        if term not in terms:
            terms.append(term)
    return terms


def _collect_terms_matching_top_tokens(tag_model, token_weights, limit=120):
    if not token_weights:
        return []
    top_tokens = [
        token
        for token, _ in sorted(token_weights.items(), key=lambda item: item[1], reverse=True)[:240]
    ]
    try:
        return list(
            tag_model.objects.filter(name__in=top_tokens)
            .order_by("-count", "name")
            .values_list("name", flat=True)[:limit]
        )
    except Exception:
        logger.warning("Could not query tag model %r for matching tokens", tag_model, exc_info=True)
        return []


def _score_candidate_term(term, token_weights, raw_text, *, scope=TaxonomySynonymGroup.Scope.ALL):
    normalized = term.replace("/", " ").replace("-", " ").replace("_", " ").lower()
    term_tokens = _tokenize_text(normalized)
    if not term_tokens:
        return 0.0

    expanded_term_tokens = expand_terms(term_tokens, scope=scope, include_original=True)
    token_scores = [token_weights.get(token, 0.0) for token in expanded_term_tokens]
    matched_scores = [score for score in token_scores if score > 0]
    if not matched_scores:
        return 0.0

    score = sum(matched_scores)
    coverage = len(matched_scores) / max(len(expanded_term_tokens), 1)
    score *= 0.55 + (0.45 * coverage)

    lowered_text = raw_text.lower()

    phrase_pattern = rf"\b{re.escape(' '.join(term_tokens))}\b"
    phrase_hits = len(re.findall(phrase_pattern, lowered_text))
    if phrase_hits:
        score += 0.9 + min(phrase_hits * 0.3, 1.8)

    if all(token in lowered_text for token in term_tokens):
        score += 0.35 + (0.2 * coverage)

    score += min(len(term_tokens) * 0.05, 0.25)
    return score


def _rule_terms(token_weights, rule_map):
    hits = set()
    active_tokens = set(token_weights.keys())
    for term, triggers in rule_map.items():
        if active_tokens & triggers:
            hits.add(term)
    return hits


def _rank_auto_terms(
    candidates,
    token_weights,
    raw_text,
    max_items,
    min_score,
    *,
    scope=TaxonomySynonymGroup.Scope.ALL,
):
    scored = []
    for candidate in candidates:
        score = _score_candidate_term(candidate, token_weights, raw_text, scope=scope)
        if score >= min_score:
            scored.append((score, candidate))
    scored.sort(key=lambda row: (row[0], len(row[1])), reverse=True)
    return [term for _, term in scored[:max_items]]


def _expand_category_ancestors(categories: set[str]):
    expanded = set()
    for category in categories:
        parts = [part for part in category.split("/") if part]
        for depth in range(1, len(parts) + 1):
            expanded.add("/".join(parts[:depth]))
    return expanded


def _rank_terms_by_relevance(
    terms,
    token_weights,
    raw_text,
    *,
    scope=TaxonomySynonymGroup.Scope.ALL,
):
    scored = [(_score_candidate_term(term, token_weights, raw_text, scope=scope), term) for term in terms]
    scored.sort(key=lambda row: (row[0], len(row[1])), reverse=True)
    return [term for _, term in scored]


def apply_auto_taxonomy_to_post(post):
    settings_payload = _get_auto_tagging_settings()
    if not settings_payload["enabled"]:
        state_changed = bool(
            (post.auto_tags or [])
            or (post.auto_categories or [])
            or (post.auto_primary_topic or "")
            or post.auto_tagging_updated_at
        )
        if state_changed:
            post.auto_tags = []
            post.auto_categories = []
            post.auto_primary_topic = ""
            post.auto_tagging_updated_at = None
            post.save(
                update_fields=[
                    "auto_tags",
                    "auto_categories",
                    "auto_primary_topic",
                    "auto_tagging_updated_at",
                ]
            )
        return {
            "applied": False,
            "reason": "disabled",
            "tags": [],
            "categories": [],
            "topic": "",
            "state_cleared": state_changed,
        }

    token_weights = _weighted_token_profile(post)
    tag_weights = augment_weighted_terms(token_weights, scope=TaxonomySynonymGroup.Scope.TAGS)
    category_weights = augment_weighted_terms(
        token_weights,
        scope=TaxonomySynonymGroup.Scope.CATEGORIES,
    )
    topic_weights = augment_weighted_terms(token_weights, scope=TaxonomySynonymGroup.Scope.TOPICS)
    raw_text = " ".join(part for part in [post.title or "", post.excerpt or "", post.body_markdown or ""] if part)

    tag_candidates = _collect_candidate_terms(Post.tags.tag_model, AUTO_TAG_RULES.keys())
    token_matched_tags = _collect_terms_matching_top_tokens(Post.tags.tag_model, tag_weights)
    category_candidates = _collect_candidate_terms(
        Post.categories.tag_model,
        AUTO_CATEGORY_RULES.keys(),
    )
    topic_candidates = _collect_candidate_terms(Post.primary_topic.tag_model, AUTO_TOPIC_RULES.keys(), limit=80)

    rule_tags = _rule_terms(token_weights, AUTO_TAG_RULES)
    rule_categories = _rule_terms(token_weights, AUTO_CATEGORY_RULES)
    rule_topics = _rule_terms(token_weights, AUTO_TOPIC_RULES)

    ranked_tags = _rank_auto_terms(
        list(dict.fromkeys(list(rule_tags) + token_matched_tags + tag_candidates)),
        tag_weights,
        raw_text,
        max_items=settings_payload["max_tags"],
        min_score=settings_payload["min_score"],
        scope=TaxonomySynonymGroup.Scope.TAGS,
    )
    ranked_categories = _rank_auto_terms(
        list(dict.fromkeys(list(rule_categories) + category_candidates)),
        category_weights,
        raw_text,
        max_items=settings_payload["max_categories"],
        min_score=settings_payload["min_score"],
        scope=TaxonomySynonymGroup.Scope.CATEGORIES,
    )
    ranked_topics = _rank_auto_terms(
        list(dict.fromkeys(list(rule_topics) + topic_candidates)),
        topic_weights,
        raw_text,
        max_items=1,
        min_score=max(settings_payload["min_score"] - 0.35, 0.4),
        scope=TaxonomySynonymGroup.Scope.TOPICS,
    )
    auto_topic = ranked_topics[0] if ranked_topics else ""

    previous_auto_tags = set(post.auto_tags or [])
    previous_auto_categories = set(post.auto_categories or [])
    previous_auto_topic = post.auto_primary_topic or ""

    current_tags = {tag.name for tag in post.tags.all()}
    current_categories = {category.name for category in post.categories.all()}
    current_topic = post.primary_topic.name if post.primary_topic else ""

    manual_tags = current_tags - previous_auto_tags
    manual_categories = current_categories - previous_auto_categories
    manual_topic = current_topic if current_topic and current_topic != previous_auto_topic else ""

    ranked_manual_tags = _rank_terms_by_relevance(
        manual_tags,
        tag_weights,
        raw_text,
        scope=TaxonomySynonymGroup.Scope.TAGS,
    )
    ranked_auto_tags = [tag for tag in ranked_tags if tag not in manual_tags]

    final_tags = []
    for tag in ranked_manual_tags + ranked_auto_tags:
        if tag not in final_tags:
            final_tags.append(tag)
        if len(final_tags) >= settings_payload["max_total_tags"]:
            break

    merged_categories = manual_categories | set(ranked_categories)
    final_categories = sorted(_expand_category_ancestors(merged_categories))
    final_topic = manual_topic or auto_topic

    post.tags.set_tag_string(",".join(final_tags))
    post.categories.set_tag_string(",".join(final_categories))
    post.primary_topic = final_topic
    post.auto_tags = ranked_tags
    post.auto_categories = ranked_categories
    post.auto_primary_topic = auto_topic
    post.auto_tagging_updated_at = timezone.now()
    post.save(
        update_fields=[
            "primary_topic",
            "auto_tags",
            "auto_categories",
            "auto_primary_topic",
            "auto_tagging_updated_at",
            "updated_at",
        ]
    )
    warm_post_vector_cache(post)

    return {
        "applied": True,
        "reason": "ok",
        "tags": ranked_tags,
        "categories": ranked_categories,
        "topic": auto_topic,
    }


def apply_post_filters(queryset, params):
    query = params.get("q", "").strip()
    if query:
        queryset = queryset.search(query)

    topic = params.get("topic", "").strip()
    if topic:
        queryset = queryset.filter(primary_topic__name__iexact=topic)

    tag = params.get("tag", "").strip()
    if tag:
        queryset = queryset.filter(tags__name__iexact=tag)

    category = params.get("category", "").strip()
    if category:
        category_match = Post.categories.tag_model.objects.filter(name__iexact=category).with_descendants()
        if category_match.exists():
            queryset = queryset.filter(categories__in=category_match)
        else:
            queryset = queryset.filter(categories__name__iexact=category)

    featured = params.get("featured", "")
    if featured in {"1", "true", "on", "yes"}:
        queryset = queryset.filter(is_featured=True)

    mode = params.get("mode", "all")
    if mode == "editors":
        queryset = queryset.filter(is_editors_pick=True)
    elif mode == "featured":
        queryset = queryset.filter(is_featured=True)

    queryset = queryset.with_reaction_counts()

    sort = params.get("sort", "latest")
    if sort == "trending":
        queryset = queryset.order_by(
            "-like_total",
            "-comment_total",
            "-views_count",
            "-published_at",
            "-created_at",
        )
    elif sort == "popular":
        queryset = queryset.order_by(
            "-views_count",
            "-bookmark_total",
            "-like_total",
            "-published_at",
            "-created_at",
        )
    else:
        queryset = queryset.order_by("-published_at", "-created_at")

    return queryset.distinct()


def get_sidebar_data():
    try:
        tag_cloud = Post.tags.tag_model.objects.weight(min=1, max=6).order_by("-count", "name")[:36]
        topic_cloud = Post.primary_topic.tag_model.objects.weight(min=1, max=6).order_by("-count", "name")[:20]
        category_tree = Post.categories.tag_model.objects.as_nested_list()
    except Exception:
        logger.warning("Failed to load sidebar tag/topic/category data", exc_info=True)
        tag_cloud = []
        topic_cloud = []
        category_tree = []

    return {
        "tag_cloud": tag_cloud,
        "topic_cloud": topic_cloud,
        "category_tree": category_tree,
    }


def get_tagulous_live_metrics(limit=10):
    def serialize_tag(tag):
        return {
            "name": tag.name,
            "label": getattr(tag, "label", tag.name),
            "count": getattr(tag, "count", 0),
            "weight": getattr(tag, "weight", None),
            "level": getattr(tag, "level", None),
        }

    metrics = {
        "top_tags": [],
        "top_topics": [],
        "top_categories": [],
        "max_category_depth_live": 0,
    }
    try:
        top_tags = list(Post.tags.tag_model.objects.weight(min=1, max=6).order_by("-count", "name")[:limit])
        top_topics = list(
            Post.primary_topic.tag_model.objects.weight(min=1, max=6).order_by("-count", "name")[:limit]
        )
        top_categories = list(Post.categories.tag_model.objects.order_by("-count", "name")[:limit])
        deepest = Post.categories.tag_model.objects.order_by("-level").first()
        metrics.update(
            {
                "top_tags": [serialize_tag(tag) for tag in top_tags],
                "top_topics": [serialize_tag(tag) for tag in top_topics],
                "top_categories": [serialize_tag(tag) for tag in top_categories],
                "max_category_depth_live": deepest.level if deepest else 0,
            }
        )
    except Exception:
        logger.warning("Failed to load extended tag/topic/category metrics", exc_info=True)

    return metrics


def get_home_metrics():
    published_qs = Post.objects.published()
    return {
        "metric_posts": published_qs.count(),
        "metric_authors": published_qs.values("author_id").distinct().count(),
        "metric_views": published_qs.aggregate(total=Sum("views_count"))["total"] or 0,
        "metric_subscribers": NewsletterSubscriber.objects.filter(is_active=True).count(),
    }


def get_listing_context(request, forced_filters=None, per_page=9):
    params = request.GET.copy()
    if forced_filters:
        for key, value in forced_filters.items():
            params[key] = value

    filter_form = PostFilterForm(params or None)

    base_qs = (
        Post.objects.select_related("author", "primary_topic")
        .prefetch_related("tags", "categories")
        .visible_to(request.user)
    )
    filtered_qs = apply_post_filters(base_qs, params)

    paginator = Paginator(filtered_qs, per_page)
    page_obj = paginator.get_page(params.get("page", 1))
    page_posts = list(page_obj.object_list)

    try:
        from core.models import FeatureControlSettings

        global_reactions_enabled = FeatureControlSettings.get_solo().enable_reactions
    except Exception:
        logger.warning("Could not read FeatureControlSettings.enable_reactions; defaulting to True", exc_info=True)
        global_reactions_enabled = True

    liked_ids: set[int] = set()
    bookmarked_ids: set[int] = set()
    if request.user.is_authenticated and page_posts:
        post_ids = [post.id for post in page_posts]
        liked_ids = set(
            PostLike.objects.filter(user=request.user, post_id__in=post_ids).values_list(
                "post_id",
                flat=True,
            )
        )
        bookmarked_ids = set(
            PostBookmark.objects.filter(
                user=request.user,
                post_id__in=post_ids,
            ).values_list("post_id", flat=True)
        )

    for post in page_posts:
        post.user_liked = post.id in liked_ids
        post.user_bookmarked = post.id in bookmarked_ids

    query_without_page = params.copy()
    query_without_page.pop("page", None)

    hero_qs = base_qs.published().order_by("-is_featured", "-published_at", "-created_at")

    related_seed = params.get("q", "").strip()
    if not related_seed:
        related_seed = " ".join(
            part
            for part in [
                params.get("topic", "").strip(),
                params.get("tag", "").strip(),
                params.get("category", "").strip(),
            ]
            if part
        )

    related_ranked = get_related_posts_algorithmic(
        request.user,
        query_text=related_seed,
        limit=5,
        with_explanations=True,
    )

    return {
        "page_obj": page_obj,
        "posts": page_posts,
        "global_reactions_enabled": global_reactions_enabled,
        "filter_form": filter_form,
        "query_without_page": query_without_page.urlencode(),
        "featured_posts": hero_qs.filter(is_featured=True)[:5],
        "editors_posts": hero_qs.filter(is_editors_pick=True)[:4],
        "trending_posts": Post.objects.published()
        .with_reaction_counts()
        .order_by("-like_total", "-comment_total", "-views_count", "-published_at")[:5],
        "fresh_posts": hero_qs[:5],
        "related_posts": [item["post"] for item in related_ranked],
        "related_posts_explain": related_ranked,
        "active_topic": params.get("topic", "").strip(),
        "active_tag": params.get("tag", "").strip(),
        "active_category": params.get("category", "").strip(),
        "active_query": params.get("q", "").strip(),
        "active_mode": params.get("mode", "all"),
        **get_home_metrics(),
        **get_sidebar_data(),
    }


def get_dashboard_metrics(user):
    scoped_posts = get_dashboard_post_queryset(user)
    published = scoped_posts.filter(status=Post.Status.PUBLISHED)
    scope = "all" if bool(user and user.is_authenticated and user.is_staff) else "mine"

    return {
        "dashboard_scope": scope,
        "dashboard_total_posts": scoped_posts.count(),
        "dashboard_published_posts": published.count(),
        "dashboard_draft_posts": scoped_posts.filter(status=Post.Status.DRAFT).count(),
        "dashboard_total_views": published.aggregate(total=Sum("views_count"))["total"] or 0,
        "dashboard_top_posts": published.order_by("-views_count", "-updated_at")[:5],
        "dashboard_latest_activity": scoped_posts.order_by("-updated_at")[:8],
        "dashboard_tagulous": get_tagulous_live_metrics(limit=12),
    }


def get_dashboard_post_queryset(user):
    base_qs = Post.objects.all()
    if not user or not user.is_authenticated:
        return base_qs.none()
    if user.is_staff:
        return base_qs
    return base_qs.filter(author=user)


def serialize_post_for_api(post):
    return {
        "id": post.id,
        "title": post.title,
        "subtitle": post.subtitle,
        "slug": post.slug,
        "excerpt": post.excerpt,
        "url": post.get_absolute_url(),
        "author": post.author.username,
        "status": post.status,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "reading_time": post.reading_time,
        "word_count": post.word_count,
        "views_count": post.views_count,
        "is_featured": post.is_featured,
        "is_editors_pick": post.is_editors_pick,
        "primary_topic": getattr(post.primary_topic, "name", "") if post.primary_topic else "",
        "tags": [tag.name for tag in post.tags.all()],
        "categories": [category.name for category in post.categories.all()],
    }


def get_search_suggestion_context(user, query: str):
    clean_query = (query or "").strip()
    base_qs = Post.objects.visible_to(user).select_related("author").prefetch_related("tags")

    if clean_query:
        search_posts = (
            base_qs.filter(
                Q(title__icontains=clean_query)
                | Q(subtitle__icontains=clean_query)
                | Q(excerpt__icontains=clean_query)
                | Q(body_markdown__icontains=clean_query)
            )
            .order_by("-published_at", "-created_at")
            .distinct()[:6]
        )
        search_total = base_qs.search(clean_query).distinct().count()
    else:
        search_posts = base_qs.order_by("-published_at", "-created_at")[:6]
        search_total = None

    tags = []
    categories = []
    topics = []
    try:
        tag_qs = Post.tags.tag_model.objects
        cat_qs = Post.categories.tag_model.objects
        topic_qs = Post.primary_topic.tag_model.objects
        if clean_query:
            tags = list(tag_qs.filter(name__icontains=clean_query).order_by("-count", "name")[:8])
            categories = list(cat_qs.filter(name__icontains=clean_query).order_by("-count", "name")[:8])
            topics = list(topic_qs.filter(name__icontains=clean_query).order_by("-count", "name")[:8])
        else:
            tags = list(tag_qs.order_by("-count", "name")[:8])
            categories = list(cat_qs.order_by("-count", "name")[:8])
            topics = list(topic_qs.order_by("-count", "name")[:8])
    except Exception:
        logger.warning("Failed to load tag/category/topic suggestions for search query %r", clean_query, exc_info=True)

    return {
        "search_query": clean_query,
        "search_total": search_total,
        "search_posts": search_posts,
        "search_tags": tags,
        "search_categories": categories,
        "search_topics": topics,
    }


# ============================================================================
# BULK OPERATIONS - Business logic for bulk actions
# ============================================================================

def bulk_change_post_status(post_ids: list[int], new_status: str) -> tuple[int, str]:
    """
    Bulk change status of posts.

    Args:
        post_ids: List of post IDs
        new_status: New status (draft, review, published, archived)

    Returns:
        (count_updated, status_name)
    """
    valid_statuses = {choice[0] for choice in Post.Status.choices}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}")

    count = Post.objects.filter(id__in=post_ids).update(
        status=new_status,
        updated_at=timezone.now()
    )

    return count, new_status


def bulk_publish_posts(post_ids: list[int], publish_at: datetime | None = None) -> int:
    """
    Bulk publish posts immediately or at a specified time.

    Args:
        post_ids: List of post IDs
        publish_at: Optional datetime to schedule publication (defaults to now)

    Returns:
        Count of posts updated
    """
    if publish_at is None:
        publish_at = timezone.now()

    count = Post.objects.filter(id__in=post_ids).update(
        status=Post.Status.PUBLISHED,
        published_at=publish_at,
        updated_at=timezone.now()
    )

    return count


def bulk_archive_posts(post_ids: list[int]) -> int:
    """Archive posts (hide from public, keep for posterity)."""
    count = Post.objects.filter(id__in=post_ids).update(
        status=Post.Status.ARCHIVED,
        updated_at=timezone.now()
    )
    return count


def bulk_unpublish_posts(post_ids: list[int]) -> int:
    """Unpublish posts, revert to draft status."""
    count = Post.objects.filter(id__in=post_ids).update(
        status=Post.Status.DRAFT,
        updated_at=timezone.now()
    )
    return count


def bulk_tag_posts(post_ids: list[int], tag_names: list[str]) -> int:
    """
    Add tags to multiple posts.

    Args:
        post_ids: List of post IDs
        tag_names: List of tag names to add

    Returns:
        Count of posts updated
    """
    posts = Post.objects.filter(id__in=post_ids)
    count = 0
    for post in posts:
        for tag_name in tag_names:
            post.tags.add(tag_name)
        count += 1
    return count


def bulk_categorize_posts(post_ids: list[int], category_names: list[str]) -> int:
    """
    Add categories to multiple posts.

    Args:
        post_ids: List of post IDs
        category_names: List of category names to add

    Returns:
        Count of posts updated
    """
    posts = Post.objects.filter(id__in=post_ids)
    count = 0
    for post in posts:
        for cat_name in category_names:
            post.categories.add(cat_name)
        count += 1
    return count


def bulk_feature_posts(post_ids: list[int], is_featured: bool = True) -> int:
    """Set featured status for multiple posts."""
    count = Post.objects.filter(id__in=post_ids).update(is_featured=is_featured)
    return count


def bulk_editors_pick_posts(post_ids: list[int], is_pick: bool = True) -> int:
    """Set editor's pick status for multiple posts."""
    count = Post.objects.filter(id__in=post_ids).update(is_editors_pick=is_pick)
    return count


def bulk_delete_posts(post_ids: list[int]) -> tuple[int, dict[str, int]]:
    """
    Permanently delete posts (hard delete).

    Args:
        post_ids: List of post IDs

    Returns:
        (count_deleted, deletion_details)
    """
    count, details = Post.objects.filter(id__in=post_ids).delete()
    return count, details
