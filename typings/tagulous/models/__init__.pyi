# Tagulous models stubs — covers BaseTagModel, TagModel, TagTreeModel,
# TagField (M2M), TreeTagField (tree M2M), SingleTagField (FK-like).
#
# Descriptor overloads are the key: Pylance uses the `instance: None`
# branch for class-level access (Post.tags → TagField, exposes .tag_model),
# and the `instance: Model` branch for instance-level access
# (post.tags → TagRelatedManager, exposes .all(), .set_tag_string(), etc.).

from __future__ import annotations

from typing import Any, ClassVar, overload

from django.db import models
from django.db.models import Manager, QuerySet


# ---------------------------------------------------------------------------
# Base tag model and QuerySet
# ---------------------------------------------------------------------------

class TagModelQuerySet(QuerySet["BaseTagModel"]):
    def initial(self) -> TagModelQuerySet: ...
    def weight(self, min: int = ..., max: int = ...) -> TagModelQuerySet: ...


class BaseTagModelManager(Manager["BaseTagModel"]):
    def get_queryset(self) -> TagModelQuerySet: ...


class BaseTagModel(models.Model):
    name: str
    slug: str
    count: int
    objects: ClassVar[Manager[BaseTagModel]]  # type: ignore[assignment]


class TagModel(BaseTagModel):
    objects: ClassVar[Manager[TagModel]]  # type: ignore[assignment]


class BaseTagTreeModel(TagModel):
    parent: BaseTagTreeModel | None
    path: str
    label: str
    level: int
    objects: ClassVar[Manager[BaseTagTreeModel]]  # type: ignore[assignment]

    def get_descendants(self) -> QuerySet[BaseTagTreeModel]: ...
    def get_ancestors(self) -> QuerySet[BaseTagTreeModel]: ...
    def get_children(self) -> QuerySet[BaseTagTreeModel]: ...


class TagTreeModel(BaseTagTreeModel): ...


# ---------------------------------------------------------------------------
# Instance-level manager returned when accessing tag fields on a model instance
# ---------------------------------------------------------------------------

class TagRelatedManager:
    """Returned by TagField.__get__ when accessed on a model instance."""

    tag_model: type[BaseTagModel]

    def all(self) -> QuerySet[BaseTagModel]: ...
    def filter(self, **kwargs: Any) -> QuerySet[BaseTagModel]: ...
    def exclude(self, **kwargs: Any) -> QuerySet[BaseTagModel]: ...
    def set_tag_string(self, tags: str) -> None: ...
    def get_tag_string(self) -> str: ...


# ---------------------------------------------------------------------------
# Field descriptors
# ---------------------------------------------------------------------------

class TagField:
    """
    Many-to-many Tagulous tag field.

    Class-level access (Post.tags) returns TagField itself — use .tag_model.
    Instance-level access (post.tags) returns TagRelatedManager.
    """

    tag_model: type[BaseTagModel]

    def __init__(self, to: Any = ..., **kwargs: Any) -> None: ...

    @overload
    def __get__(self, instance: None, owner: type[Any]) -> TagField: ...
    @overload
    def __get__(self, instance: models.Model, owner: type[Any]) -> TagRelatedManager: ...
    def __get__(
        self, instance: models.Model | None, owner: type[Any]
    ) -> TagField | TagRelatedManager: ...
    def __set__(self, instance: models.Model, value: Any) -> None: ...


class TreeTagField(TagField):
    """
    Tree-structured many-to-many Tagulous tag field.
    Behaves identically to TagField from a typing perspective.
    """
    ...


class SingleTagField:
    """
    Single-value Tagulous tag field (FK-like).

    Class-level access (Post.primary_topic) returns SingleTagField — use .tag_model.
    Instance-level access (post.primary_topic) returns the tag model instance or None.
    """

    tag_model: type[BaseTagModel]

    def __init__(self, to: Any = ..., **kwargs: Any) -> None: ...

    @overload
    def __get__(self, instance: None, owner: type[Any]) -> SingleTagField: ...
    @overload
    def __get__(self, instance: models.Model, owner: type[Any]) -> BaseTagModel | None: ...
    def __get__(
        self, instance: models.Model | None, owner: type[Any]
    ) -> SingleTagField | BaseTagModel | None: ...
    def __set__(self, instance: models.Model, value: Any) -> None: ...


# Convenience re-exports used by admin and views
__all__ = [
    "BaseTagModel",
    "TagModel",
    "TagTreeModel",
    "BaseTagTreeModel",
    "TagField",
    "TreeTagField",
    "SingleTagField",
    "TagRelatedManager",
    "TagModelQuerySet",
    "BaseTagModelManager",
]
