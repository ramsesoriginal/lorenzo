from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base
from lorenzo_api.models.item_view_mixin import ItemViewMixin

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class VItem(ItemViewMixin, Base):
    """Read-only view over every base item-typed entity (the `item` table
    only, not `item_instance`) - see ADR 0019. No real constraints (views
    can't have any); `entity_id` is declared primary_key=True purely so the
    ORM has an identity to key on, matching no actual PRIMARY KEY
    constraint in the database.
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
    # since that's the one hop every ItemViewMixin property needs; loading
    # further (entity.information/.stats and their own nested relationships)
    # is left to the caller rather than guessed at by a default here.
    entity: Mapped[Entity] = relationship(
        primaryjoin="VItem.entity_id == Entity.id",
        foreign_keys=[entity_id],
        viewonly=True,
        lazy="selectin",
    )
