from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base
from lorenzo_api.models.entity_view_mixin import EntityViewMixin

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class VCharacter(EntityViewMixin, Base):
    """Read-only view over every character-typed entity - see ADR 0031/RFC
    0004. Mirrors VItem/VItemInstance (ADR 0019): `owner_player_id` is
    "the one column genuinely specific to this view", the same role
    `VItemInstance.owner_entity_id` plays there. Deliberately no
    RPG-flavored stat columns (an `hp`, say) - `v_item`'s own weight/
    price/rarity/hp/armor were specific choices for that slice, not a
    template; which stats matter enough for a dedicated column on
    `v_character` is a product call this RFC doesn't make. Anything beyond
    these columns stays reachable through EntityViewMixin's shared
    stat-group properties.

    No real constraints (views can't have any); `entity_id` is declared
    primary_key=True purely so the ORM has an identity to key on, matching
    no actual PRIMARY KEY constraint in the database.
    """

    __tablename__ = "v_character"

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID]
    owner_player_id: Mapped[uuid.UUID | None]
    description_id: Mapped[uuid.UUID | None]
    title: Mapped[str | None]
    container_entity_id: Mapped[uuid.UUID | None]

    # See VItem for why this needs an explicit primaryjoin/foreign_keys=
    # and lazy="selectin".
    entity: Mapped[Entity] = relationship(
        primaryjoin="VCharacter.entity_id == Entity.id",
        foreign_keys=[entity_id],
        viewonly=True,
        lazy="selectin",
    )
