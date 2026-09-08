import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class StatValueType(enum.Enum):
    """Which of entity_stat's value_* columns a stat's value lives in."""

    INT = "int"
    TEXT = "text"
    FLOAT = "float"
    BOOL = "bool"


class StatDefinition(Base):
    """Describes a single stat (weight, HP, ...) - see ADR 0014 and RFC 0001."""

    __tablename__ = "stat_definition"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )
    stat_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stat_group.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[StatValueType] = mapped_column(
        Enum(
            StatValueType,
            name="stat_value_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )
