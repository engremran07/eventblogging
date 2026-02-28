from __future__ import annotations

from collections.abc import Iterable

from django.core.exceptions import ValidationError
from tagulous.utils import split_tree_name

from core.models import FeatureControlSettings

DEFAULT_CATEGORY_MAX_DEPTH = 5
MIN_CATEGORY_MAX_DEPTH = 1
MAX_CATEGORY_MAX_DEPTH = 10


def clamp_category_max_depth(value: int | None) -> int:
    if value is None:
        return DEFAULT_CATEGORY_MAX_DEPTH
    try:
        depth = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CATEGORY_MAX_DEPTH
    return max(MIN_CATEGORY_MAX_DEPTH, min(MAX_CATEGORY_MAX_DEPTH, depth))


def get_category_max_depth() -> int:
    try:
        controls = FeatureControlSettings.get_solo()
    except Exception:
        return DEFAULT_CATEGORY_MAX_DEPTH
    return clamp_category_max_depth(getattr(controls, "category_max_depth", None))


def category_depth_help_text(max_depth: int | None = None) -> str:
    depth = clamp_category_max_depth(max_depth) if max_depth is not None else get_category_max_depth()
    examples = "/".join(f"level{i}" for i in range(1, depth + 1))
    return f"Nested categories are supported up to depth {depth} (e.g. {examples})."


def split_category_string(raw_value: str) -> list[str]:
    return [item.strip() for item in (raw_value or "").split(",") if item.strip()]


def find_categories_over_max_depth(
    category_names: Iterable[str],
    max_depth: int | None = None,
) -> list[str]:
    depth = clamp_category_max_depth(max_depth) if max_depth is not None else get_category_max_depth()
    too_deep: list[str] = []
    for category_name in category_names:
        name = (category_name or "").strip()
        if not name:
            continue
        if len(split_tree_name(name)) > depth:
            too_deep.append(name)
    return sorted(set(too_deep))


def validate_category_depth(
    category_names: Iterable[str],
    max_depth: int | None = None,
) -> None:
    depth = clamp_category_max_depth(max_depth) if max_depth is not None else get_category_max_depth()
    too_deep = find_categories_over_max_depth(category_names, max_depth=depth)
    if too_deep:
        raise ValidationError(
            f"Category nesting is limited to {depth} levels. Too deep: {', '.join(too_deep)}"
        )
