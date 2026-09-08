import uuid

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class EntityPrototype(Base):
    """An entity's prototypes (the inheritance graph) - see ADR 0015 and RFC
    0001. Cycle prevention: direct self-loops are rejected by the CHECK
    below; transitive cycles are rejected by a BEFORE INSERT trigger (see the
    migration) that this model can't express.
    """

    __tablename__ = "entity_prototype"
    __table_args__ = (
        CheckConstraint("entity_id <> prototype_id", name="entity_prototype_no_self_loop"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity.id"), primary_key=True
    )
    prototype_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity.id"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )
