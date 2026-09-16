from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.character import Character
    from lorenzo_api.models.entity import Entity


class GroupMember(Base):
    """Membership of a character in a group knower - see RFC 0001's
    knowledge design (a group is a bare Entity with no dedicated concrete
    table) and ADR 0028. group_entity_id is a plain FK -> entity.id (any
    entity can be used as a group); character_entity_id FKs to
    character.entity_id specifically (retargeted from being.entity_id by
    ADR 0031/RFC 0004 - a being now has to be "promoted" to a character
    row before it can be group-linked, a deliberate tightening from ADR
    0028's original design), matching CharacterPlayer's own precedent
    that a "character_entity_id"-named column always targets a tracked
    character, not a bare Being.

    The CHECK below rejects the direct self-loop case where an entity that
    also happens to have a Character row (RFC 0001: an entity isn't
    limited to one concrete table) is listed as its own member - a real,
    reachable case, not hypothetical. No recursive-cycle trigger is needed
    unlike EntityPrototype: this table's bipartite shape (the group side
    ranges over all entities, the member side only over characters) can't
    otherwise form a multi-hop cycle.
    """

    __tablename__ = "group_member"
    __table_args__ = (
        CheckConstraint("group_entity_id <> character_entity_id", name="group_member_no_self_loop"),
    )

    group_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    character_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("character.entity_id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]

    group: Mapped[Entity] = relationship(lazy="raise_on_sql", back_populates="group_member_links")
    character: Mapped[Character] = relationship(lazy="raise_on_sql", back_populates="group_links")
