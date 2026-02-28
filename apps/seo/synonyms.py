from __future__ import annotations

from collections import Counter
from functools import lru_cache

from .models import TaxonomySynonymGroup

SCOPE_PRIORITY = {
    TaxonomySynonymGroup.Scope.CATEGORIES: 4,
    TaxonomySynonymGroup.Scope.TOPICS: 3,
    TaxonomySynonymGroup.Scope.TAGS: 2,
    TaxonomySynonymGroup.Scope.ALL: 1,
}


def normalize_term(value: str):
    return " ".join((value or "").strip().lower().split())


def _scope_group_order(scope: str):
    if scope == TaxonomySynonymGroup.Scope.CATEGORIES:
        return [TaxonomySynonymGroup.Scope.CATEGORIES, TaxonomySynonymGroup.Scope.ALL]
    if scope == TaxonomySynonymGroup.Scope.TOPICS:
        return [TaxonomySynonymGroup.Scope.TOPICS, TaxonomySynonymGroup.Scope.ALL]
    if scope == TaxonomySynonymGroup.Scope.TAGS:
        return [TaxonomySynonymGroup.Scope.TAGS, TaxonomySynonymGroup.Scope.ALL]
    return [
        TaxonomySynonymGroup.Scope.CATEGORIES,
        TaxonomySynonymGroup.Scope.TOPICS,
        TaxonomySynonymGroup.Scope.TAGS,
        TaxonomySynonymGroup.Scope.ALL,
    ]


def _pick_canonical(terms):
    ranked = sorted(
        terms,
        key=lambda row: (bool(row.is_canonical), float(row.weight), row.term),
        reverse=True,
    )
    return ranked[0] if ranked else None


@lru_cache(maxsize=8)
def _synonym_index_for_scope(scope: str):
    allowed_scopes = _scope_group_order(scope)
    groups = (
        TaxonomySynonymGroup.objects.filter(is_active=True, scope__in=allowed_scopes)
        .prefetch_related("terms")
        .order_by("name")
    )
    index = {}
    for group in groups:
        terms = [term for term in group.terms.all() if term.is_active]
        if not terms:
            continue
        canonical = _pick_canonical(terms)
        normalized_terms = {term.normalized_term for term in terms if term.normalized_term}
        if not normalized_terms:
            continue
        scope_priority = SCOPE_PRIORITY.get(group.scope, 0)
        canonical_label = canonical.term if canonical else ""
        canonical_norm = canonical.normalized_term if canonical else ""
        for term in terms:
            norm = term.normalized_term
            if not norm:
                continue
            candidate = {
                "canonical": canonical_label,
                "canonical_normalized": canonical_norm,
                "expanded_terms": set(normalized_terms),
                "scope": group.scope,
                "priority": scope_priority,
                "weight": float(term.weight),
            }
            existing = index.get(norm)
            if not existing:
                index[norm] = candidate
                continue
            existing_rank = (int(existing["priority"]), float(existing["weight"]))
            candidate_rank = (int(candidate["priority"]), float(candidate["weight"]))
            if candidate_rank > existing_rank:
                index[norm] = candidate
    return index


def clear_synonym_cache():
    _synonym_index_for_scope.cache_clear()


def synonym_entry(term: str, *, scope: str = TaxonomySynonymGroup.Scope.ALL):
    return _synonym_index_for_scope(scope).get(normalize_term(term))


def canonical_term(term: str, *, scope: str = TaxonomySynonymGroup.Scope.ALL):
    entry = synonym_entry(term, scope=scope)
    if not entry:
        return ""
    return entry.get("canonical", "")


def expand_terms(
    terms,
    *,
    scope: str = TaxonomySynonymGroup.Scope.ALL,
    include_original: bool = True,
):
    expanded = set()
    index = _synonym_index_for_scope(scope)
    for raw in terms or []:
        norm = normalize_term(raw)
        if not norm:
            continue
        if include_original:
            expanded.add(norm)
        entry = index.get(norm)
        if entry:
            expanded.update(entry.get("expanded_terms", set()))
            canonical_norm = entry.get("canonical_normalized")
            if canonical_norm:
                expanded.add(canonical_norm)
    return expanded


def augment_weighted_terms(
    token_weights,
    *,
    scope: str = TaxonomySynonymGroup.Scope.ALL,
    expansion_factor: float = 0.55,
):
    weighted = Counter(token_weights or {})
    index = _synonym_index_for_scope(scope)
    for raw_term, raw_weight in list(weighted.items()):
        weight = float(raw_weight or 0.0)
        if weight <= 0:
            continue
        norm = normalize_term(raw_term)
        if not norm:
            continue
        entry = index.get(norm)
        if not entry:
            continue
        expanded_terms = entry.get("expanded_terms", set()) or set()
        if not expanded_terms:
            continue
        per_term_boost = (weight * expansion_factor) / max(len(expanded_terms), 1)
        for expanded in expanded_terms:
            if expanded == norm:
                continue
            weighted[expanded] += per_term_boost
        canonical_norm = entry.get("canonical_normalized")
        if canonical_norm and canonical_norm != norm:
            weighted[canonical_norm] += weight * 0.2
    return weighted

