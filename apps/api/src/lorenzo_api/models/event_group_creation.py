"""Retry receipt for a local group creation action; not repository content (ADR 0316)."""

import uuid

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedBy, TenantFk, same_tenant_fk


class EventGroupCreation(Base):
    __tablename__ = "event_group_creation"
    __table_args__ = (
        UniqueConstraint("group_entity_id", "tenant_id", name="event_group_creation_tenant_key"),
        same_tenant_fk(
            "event_group_creation_group_fkey", ["group_entity_id"], "entity", ondelete="CASCADE"
        ),
    )
    group_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    created_by: Mapped[CreatedBy]
    request_hash: Mapped[str]
