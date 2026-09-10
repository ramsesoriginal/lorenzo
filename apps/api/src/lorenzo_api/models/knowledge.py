from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.information import Information
    from lorenzo_api.models.player import Player


class Knowledge(Base):
    """Links a knower - a character or group (both via knower_entity_id,
    disambiguated only by whether the target Entity also has a Being row),
    or a player (knower_player_id) - to a specific Information row. See RFC
    0001 and ADR 0028. Exactly one of knower_entity_id/knower_player_id is
    set per row (CHECK below, mirroring EntityStat's "exactly one of N"
    precedent, ADR 0014). "Known to everyone" doesn't use this table at
    all - see Information.is_public.

    Needs a surrogate UuidPk, unlike every other join table so far: a
    composite PK can't include the always-one-null knower columns
    (Postgres disallows NULL in PK columns). ON DELETE CASCADE is the only
    viable choice for both knower FKs (not SET NULL, unlike
    Being.owner_player_id): nulling either one out while the CHECK
    requires exactly one non-null would leave the row failing that CHECK
    at delete time, so the row has to go instead.

    The two UniqueConstraints replace the duplicate-prevention every other
    join table gets for free from a composite PK: Postgres treats NULL as
    distinct from NULL in a UNIQUE constraint by default, so
    UNIQUE(knower_entity_id, information_id) only ever collides between two
    entity-knower rows - it never interferes with player-knower rows
    (knower_entity_id IS NULL there), so several distinct knowers can still
    share the same information row (the "visible to a subset of players"
    case) without tripping either constraint.
    """

    __tablename__ = "knowledge"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(knower_entity_id, knower_player_id) = 1",
            name="knowledge_exactly_one_knower",
        ),
        UniqueConstraint(
            "knower_entity_id", "information_id", name="knowledge_unique_entity_knower_information"
        ),
        UniqueConstraint(
            "knower_player_id", "information_id", name="knowledge_unique_player_knower_information"
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    knower_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), index=True
    )
    knower_player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("player.id", ondelete="CASCADE"), index=True
    )
    information_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("information.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    knower_entity: Mapped[Entity | None] = relationship(
        lazy="raise_on_sql", back_populates="knowledge_links"
    )
    knower_player: Mapped[Player | None] = relationship(
        lazy="raise_on_sql", back_populates="knowledge_links"
    )
    information: Mapped[Information] = relationship(
        lazy="raise_on_sql", back_populates="knowledge_links"
    )
