from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.being import Being
    from lorenzo_api.models.entity import Entity


class GroupMember(Base):
    """A being in a knowledge group (ADR 0316). The member column keeps its legacy
    name for API/storage compatibility; it references Being, without requiring tracking.
    Knowledge follows direct membership only, not nested-group inheritance.
    """

    __tablename__ = "group_member"
    __table_args__ = (
        same_tenant_fk(
            "group_member_character_entity_id_fkey",
            ["character_entity_id"],
            "being",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "group_member_group_entity_id_fkey", ["group_entity_id"], "entity", ondelete="CASCADE"
        ),
        CheckConstraint("group_entity_id <> character_entity_id", name="group_member_no_self_loop"),
    )

    group_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    character_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]

    group: Mapped[Entity] = relationship(
        foreign_keys="GroupMember.group_entity_id",
        lazy="raise_on_sql",
        back_populates="group_member_links",
    )
    being: Mapped[Being] = relationship(
        foreign_keys="GroupMember.character_entity_id",
        lazy="raise_on_sql",
        back_populates="group_links",
    )
