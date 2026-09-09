from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.player import Player
    from lorenzo_api.models.tenant import Tenant


class Campaign(Base):
    """A specific play-through inside a Tenant's persistent world - a
    tenant can host more than one. See ADR 0024/RFC 0002.
    """

    __tablename__ = "campaign"

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    name: Mapped[str]
    game_system: Mapped[str]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    tenant: Mapped[Tenant] = relationship(back_populates="campaigns")
    players: Mapped[list[Player]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )
