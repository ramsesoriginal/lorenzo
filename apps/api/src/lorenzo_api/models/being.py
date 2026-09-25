from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.character import Character
    from lorenzo_api.models.entity import Entity


class Being(Base):
    """Anything sentient/agentive - a character, an NPC - see ADR 0025 and
    RFC 0001/0002. Mirrors Item's bare class-table-inheritance shape.

    `owner_player_id`/`player_links`/`group_links` moved to `Character`
    (ADR 0031/RFC 0004): only a tracked, named individual is ever
    player-owned, rostered, or knowledge-grouped - a bare, untracked
    `being` was never a meaningful target for any of the three.
    """

    __tablename__ = "being"
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint("entity_id", "tenant_id", name="being_entity_id_tenant_id_key"),
        same_tenant_fk("being_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]

    entity: Mapped[Entity] = relationship(
        foreign_keys="Being.entity_id", lazy="raise_on_sql", back_populates="being"
    )
    character: Mapped[Character | None] = relationship(
        foreign_keys="Character.entity_id",
        lazy="raise_on_sql",
        back_populates="being",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
