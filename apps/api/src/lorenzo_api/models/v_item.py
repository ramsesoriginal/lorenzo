from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class VItem(Base):
    """Read-only view over every item/item_instance entity - see ADR 0019.
    No real constraints (views can't have any); `entity_id` is declared
    primary_key=True purely so the ORM has an identity to key on, matching
    no actual PRIMARY KEY constraint in the database.

    descriptions/pictures/*_stats/tags below aren't view columns - a SQL
    view can't return a list-of-tuples in one cell - they're Python
    properties navigating Entity's own already-existing relationships.
    That means fully populating them requires eager-loading the right
    chain first (entity -> information -> payloads -> description/picture,
    and entity -> stats -> stat_definition -> stat_group); accessing them
    without doing so returns an empty list or raises, it does not silently
    lazy-load in this project's async setup (see ADR 0018's own async
    lazy-load pitfalls).
    """

    __tablename__ = "v_item"

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID]
    description_id: Mapped[uuid.UUID | None]
    title: Mapped[str | None]
    weight: Mapped[int | None]
    height: Mapped[int | None]
    price: Mapped[int | None]
    rarity: Mapped[int | None]
    hp: Mapped[int | None]
    armor: Mapped[int | None]
    container_entity_id: Mapped[uuid.UUID | None]
    is_magical: Mapped[bool | None]
    is_cursed: Mapped[bool | None]

    # No real ForeignKey (views have none) - primaryjoin/foreign_keys= spell
    # out the join explicitly instead of relying on a constraint to infer
    # it from. lazy="selectin" so entity loads automatically with VItem,
    # since that's the one hop every property below needs; loading further
    # (entity.information/.stats and their own nested relationships) is
    # left to the caller rather than guessed at by a default here.
    entity: Mapped[Entity] = relationship(
        primaryjoin="VItem.entity_id == Entity.id",
        foreign_keys=[entity_id],
        viewonly=True,
        lazy="selectin",
    )

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
