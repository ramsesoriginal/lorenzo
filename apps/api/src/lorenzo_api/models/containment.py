import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class Containment(Base):
    """Where an entity physically is - an item in a backpack, a backpack on
    a character, a character in a room - see ADR 0016 and RFC 0001. No row
    means "not contained in anything". Unlike EntityPrototype, the PK is
    child_entity_id alone: an entity has at most one direct container, so
    moving it is an UPDATE of parent_entity_id, not delete-then-insert.
    Deliberately no cycle prevention - see the ADR for why.
    """

    __tablename__ = "containment"

    child_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity.id"), primary_key=True
    )
    parent_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )
