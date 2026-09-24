from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from lorenzo_api.information_visibility import InformationVisibility
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.stat_evaluation import Value


class EntityViewMixin:
    """Shared by VItem, VItemInstance, and VCharacter - see ADR 0019/0031.
    Plain Python properties/methods navigating Entity's own already-existing
    relationships, not SQLAlchemy relationship()s of their own - a SQL view
    can't return a list-of-tuples in one cell, and duplicating a multi-hop
    join condition per property would be riskier than reusing relationships
    already built and tested elsewhere.

    Renamed from ItemViewMixin (ADR 0031/RFC 0004): every property here was
    already generic - built on Entity's own relationships, nothing
    item-specific about the implementation, just the names of the
    stat_groups a tenant happens to use - so sharing it with VCharacter
    avoids a second, drifting copy of the identical logic.

    Requires the concrete class to provide its own `entity: Mapped[Entity]`
    relationship (not shared here, since each view's join condition differs
    - VItem via `item`, VItemInstance via `item_instance`, VCharacter via
    `character`/`being`). Fully populating these properties requires
    eager-loading entity -> information -> payloads -> description, entity
    -> information -> knowledge_links (needed by `descriptions` below - ADR
    0028), and entity -> effective_stats -> stat_definition -> stat_group;
    accessing them without doing so returns an empty list or raises, it
    does not silently lazy-load in this project's async setup (see ADR
    0018's own async lazy-load pitfalls).

    `_stats_for_group`/`tags` read `entity.effective_stats` (ADR 0039's
    resolved, prototype-inheriting view), not `entity.stats` (an entity's
    own direct rows only) - so these agree with `weight`/`hp`/`armor`/etc.
    on the same view's plain columns instead of silently disagreeing with
    them for anything inherited, the gap ADR 0037 originally left open and
    ADR 0039 closed. Values go through stat_evaluation (ADR 0104), so a
    computed stat shows its computed value; that also needs entity ->
    effective_stats -> computed_stat -> linear/comparison eager-loaded.

    No `pictures` here (unlike `descriptions`) - checked and confirmed
    unused: `schemas/items.py`'s `_picture_refs` needs the owning `Payload`
    row itself (for its id, to build a content URL), not just its bytes,
    so it always re-walked entity.information independently rather than
    calling a `pictures` property/method here. Removed rather than kept
    correct-but-orphaned once that was confirmed, not left as unreachable
    code nobody would notice going stale.
    """

    entity: Entity

    def descriptions(self, visibility: InformationVisibility) -> list[tuple[str, str]]:
        """Not a bare property - which descriptions are included depends on
        the caller (ADR 0028's addendum: the same visibility-gating
        GET /entities/{id} and GET /payloads/{id}/content already apply,
        applied here too - this was a real, confirmed gap until that fix).
        """
        return [
            (payload.description.content, payload.description.locale)
            for info in self.entity.information
            if info.type == "description" and visibility.can_see(info)
            for payload in info.payloads
            if payload.description is not None
        ]

    def resolved_stat_values(self) -> dict[uuid.UUID, Value]:
        """Every effective stat's value, computed ones included (ADR 0104) -
        see stat_evaluation.evaluate. Also needs entity -> effective_stats
        -> computed_stat -> linear/comparison eager-loaded."""
        # Imported here: stat_evaluation imports lorenzo_api.models, which
        # imports this module.
        from lorenzo_api.stat_evaluation import evaluate

        return evaluate(self.entity.effective_stats)

    def resolved_value_by_name(self, name: str) -> Value | None:
        """The value of the effective stat called `name` - how the named
        ItemOut columns (`weight`, ...) pick up a computed value their SQL
        view column can't carry (ADR 0104)."""
        values = self.resolved_stat_values()
        for stat in self.entity.effective_stats:
            if stat.stat_definition.name == name:
                return values.get(stat.stat_definition_id)
        return None

    def _stats_for_group(self, group_name: str) -> list[tuple[str, int | None]]:
        # Int values only, as before: a stat of any other type in the
        # group still appears, with None (ADR 0039's shape, unchanged).
        values = self.resolved_stat_values()
        pairs: list[tuple[str, int | None]] = []
        for stat in self.entity.effective_stats:
            if stat.stat_definition.stat_group.name != group_name:
                continue
            value = values.get(stat.stat_definition_id)
            if isinstance(value, bool) or not isinstance(value, int):
                value = None
            pairs.append((stat.stat_definition.name, value))
        return pairs

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
        values = self.resolved_stat_values()
        pairs: list[tuple[str, bool | None]] = []
        for stat in self.entity.effective_stats:
            if stat.stat_definition.stat_group.name != "tags":
                continue
            value = values.get(stat.stat_definition_id)
            pairs.append((stat.stat_definition.name, value if isinstance(value, bool) else None))
        return pairs
