from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class ItemViewMixin:
    """Shared by VItem and VItemInstance - see ADR 0019. Plain Python
    properties navigating Entity's own already-existing relationships, not
    SQLAlchemy relationship()s of their own - a SQL view can't return a
    list-of-tuples in one cell, and duplicating a multi-hop join condition
    per property would be riskier than reusing relationships already built
    and tested elsewhere.

    Requires the concrete class to provide its own `entity: Mapped[Entity]`
    relationship (not shared here, since each view's join condition differs
    - VItem via `item`, VItemInstance via `item_instance`). Fully populating
    these properties requires eager-loading entity -> information ->
    payloads -> description/picture, and entity -> stats -> stat_definition
    -> stat_group; accessing them without doing so returns an empty list or
    raises, it does not silently lazy-load in this project's async setup
    (see ADR 0018's own async lazy-load pitfalls).
    """

    entity: Entity

    @property
    def descriptions(self) -> list[tuple[str, str]]:
        return [
            (payload.description.content, payload.description.locale)
            for info in self.entity.information
            if info.type == "description"
            for payload in info.payloads
            if payload.description is not None
        ]

    @property
    def pictures(self) -> list[tuple[bytes, str]]:
        return [
            (payload.picture.data, payload.picture.file_type)
            for info in self.entity.information
            if info.type == "description"
            for payload in info.payloads
            if payload.picture is not None
        ]

    def _stats_for_group(self, group_name: str) -> list[tuple[str, int | None]]:
        return [
            (stat.stat_definition.name, stat.value_int)
            for stat in self.entity.stats
            if stat.stat_definition.stat_group.name == group_name
        ]

    @property
    def physical_stats(self) -> list[tuple[str, int | None]]:
        return self._stats_for_group("physical")

    @property
    def economic_stats(self) -> list[tuple[str, int | None]]:
        return self._stats_for_group("economic")

    @property
    def destroyable_stats(self) -> list[tuple[str, int | None]]:
        return self._stats_for_group("destroyable")

    @property
    def damaging_stats(self) -> list[tuple[str, int | None]]:
        return self._stats_for_group("damaging")

    @property
    def tags(self) -> list[tuple[str, bool | None]]:
        return [
            (stat.stat_definition.name, stat.value_bool)
            for stat in self.entity.stats
            if stat.stat_definition.stat_group.name == "tags"
        ]
