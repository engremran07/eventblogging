"""
TF-IDF module for automatic keyword extraction and tag suggestion.
Extracts top N keywords from post content and matches against existing taxonomies.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.db.models import QuerySet
from sklearn.feature_extraction.text import TfidfVectorizer

from blog.models import Post

logger = logging.getLogger(__name__)


class PostTfidfExtractor:
    """Extract TF-IDF features from post content."""

    MIN_DF = 1  # Minimum document frequency
    MAX_DF = 0.95  # Maximum document frequency
    MAX_FEATURES = 500  # Maximum number of features
    NGRAM_RANGE = (1, 2)  # Unigrams and bigrams

    def __init__(self, *, min_df: int = MIN_DF, max_df: float = MAX_DF):
        self.min_df = min_df
        self.max_df = max_df
        self.vectorizer = TfidfVectorizer(
            min_df=min_df,
            max_df=max_df,
            max_features=self.MAX_FEATURES,
            ngram_range=self.NGRAM_RANGE,
            stop_words="english",
            lowercase=True,
            strip_accents="unicode",
            decode_error="ignore",
        )
        self._fit_cache = {}

    def extract_body_text(self, post: Post) -> str:
        """Extract clean text from HTML body for analysis."""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", post.body_html or "")
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def extract_keywords(self, post: Post, top_n: int = 15) -> list[dict[str, Any]]:
        """
        Extract top N keywords from post by TF-IDF score.
        Returns list of dicts with 'term' and 'score' keys.
        """
        body_text = self.extract_body_text(post)
        if not body_text or len(body_text.split()) < 10:
            return []

        # Build a corpus of all posts for vectorizer context
        corpus = self._build_corpus()
        corpus.append(body_text)

        try:
            self.vectorizer.fit(corpus)
        except Exception:
            logger.warning("TF-IDF vectorizer fit failed", exc_info=True)
            return []

        # Transform the current post
        try:
            tfidf_matrix = self.vectorizer.transform([body_text])
        except Exception:
            logger.warning("TF-IDF vectorizer transform failed", exc_info=True)
            return []

        # Get feature names and scores
        feature_names = self.vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]

        # Create keyword list with scores
        keywords = [
            {"term": feature_names[idx], "score": float(score)}
            for idx, score in enumerate(scores)
            if score > 0
        ]

        # Sort by score descending and return top N
        keywords.sort(key=lambda x: x["score"], reverse=True)
        return keywords[:top_n]

    def _build_corpus(self, limit: int = 100) -> list[str]:
        """Build a corpus of recent published posts for TF-IDF context."""
        posts = Post.objects.published().order_by("-published_at")[:limit]
        corpus = []
        for post in posts:
            text = self.extract_body_text(post)
            if text:
                corpus.append(text)
        return corpus


def match_keywords_to_taxonomy(
    keywords: list[dict[str, Any]],
    *,
    tags_queryset: QuerySet | None = None,
    topics_queryset: QuerySet | None = None,
    categories_queryset: QuerySet | None = None,
    threshold: float = 0.3,
) -> dict[str, list[str]]:
    """
    Match extracted keywords to existing taxonomy terms.
    Uses fuzzy string matching with similarity threshold.

    Args:
        keywords: List of dicts with 'term' and 'score' keys
        tags_queryset: QuerySet of tag names
        topics_queryset: QuerySet of topic names
        categories_queryset: QuerySet of category names
        threshold: Minimum similarity score (0-1) to match

    Returns:
        Dict with 'tags', 'topics', 'categories' keys containing matched terms
    """
    from difflib import SequenceMatcher

    if not keywords:
        return {"tags": [], "topics": [], "categories": []}

    # Import here to avoid circular imports
    from blog.models import Post as PostModel

    # Default querysets if not provided
    if tags_queryset is None:
        tags_queryset = (
            PostModel.tags.through.objects.values_list("tag__name", flat=True)
            .distinct()
            .order_by("tag__name")
        )

    if topics_queryset is None:
        topics_queryset = (
            PostModel.primary_topic.through.objects.values_list("tag__name", flat=True)
            .distinct()
            .order_by("tag__name")
        )

    if categories_queryset is None:
        categories_queryset = (
            PostModel.categories.through.objects.values_list("tag__name", flat=True)
            .distinct()
            .order_by("tag__name")
        )

    results = {"tags": [], "topics": [], "categories": []}
    keyword_terms = [k["term"].lower() for k in keywords]

    # Match to taxonomy terms
    for taxonomy_name, taxonomy_set, result_key in [
        ("topics", topics_queryset, "topics"),
        ("tags", tags_queryset, "tags"),
        ("categories", categories_queryset, "categories"),
    ]:
        for tax_term in taxonomy_set:
            tax_term_lower = tax_term.lower()
            # Check for exact or partial match
            for keyword_term in keyword_terms:
                ratio = SequenceMatcher(None, keyword_term, tax_term_lower).ratio()
                if ratio >= threshold or keyword_term in tax_term_lower:
                    if tax_term not in results[result_key]:
                        results[result_key].append(tax_term)
                    break

    return results


def auto_apply_tags_to_post(post: Post, *, trust_score: float = 0.5) -> dict[str, Any]:
    """
    Auto-tag a post using TF-IDF extraction and taxonomy matching.

    Args:
        post: Post instance to tag
        trust_score: Minimum confidence to auto-apply tags (0-1)

    Returns:
        Dict with extracted keywords and matched taxonomy terms
    """
    extractor = PostTfidfExtractor()

    # Extract keywords
    keywords = extractor.extract_keywords(post, top_n=15)

    if not keywords:
        return {
            "keywords": [],
            "matched_tags": [],
            "matched_topics": [],
            "matched_categories": [],
        }

    # Match to taxonomy
    matches = match_keywords_to_taxonomy(keywords, threshold=0.3)

    # Update post auto_tags (for UI reference)
    auto_tags_data = {
        "keywords": keywords,
        "matched_tags": matches.get("tags", []),
        "matched_topics": matches.get("topics", []),
        "matched_categories": matches.get("categories", []),
    }

    return auto_tags_data


def apply_auto_tags_to_post(post: Post, *, preserve_manual: bool = True) -> None:
    """
    Apply auto-extracted tags and categories to a post.
    Can preserve existing manual tags if preserve_manual=True.

    Args:
        post: Post instance
        preserve_manual: If True, keep existing manual tags and merge with auto tags
    """
    auto_data = auto_apply_tags_to_post(post)

    # Get matched terms
    matched_topics = auto_data.get("matched_topics", [])
    matched_tags = auto_data.get("matched_tags", [])
    matched_categories = auto_data.get("matched_categories", [])

    # Apply topic
    if matched_topics and not post.primary_topic:
        post.primary_topic = matched_topics[0]
        post.auto_primary_topic = matched_topics[0]

    # Apply tags
    if matched_tags:
        if preserve_manual:
            existing_tags = set(post.tags.all().values_list("name", flat=True))
            new_tags = set(matched_tags) - existing_tags
            if new_tags:
                post.tags.add(*new_tags)
        else:
            post.tags.set(matched_tags)

    # Apply categories
    if matched_categories:
        if preserve_manual:
            existing_cats = set(post.categories.all().values_list("name", flat=True))
            new_cats = set(matched_categories) - existing_cats
            if new_cats:
                post.categories.add(*new_cats)
        else:
            post.categories.set(matched_categories)

    # Store the auto_tags data
    post.auto_tags = auto_data
    post.save(update_fields=["auto_tags", "auto_primary_topic", "updated_at"])
