"""Private acknowledgements for lossless paragraph splits (ADR 0346)."""

import uuid

from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UuidPk, same_tenant_fk


class ManuscriptSplit(Base):
    __tablename__ = "manuscript_split"
    __table_args__ = (
        same_tenant_fk("manuscript_split_entry_fkey", ["entry_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "manuscript_split_first_fkey", ["first_payload_id"], "payload", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "manuscript_split_second_fkey", ["second_payload_id"], "payload", ondelete="CASCADE"
        ),
    )
    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    entry_id: Mapped[uuid.UUID] = mapped_column(index=True)
    first_payload_id: Mapped[uuid.UUID] = mapped_column(index=True)
    second_payload_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_id: Mapped[CreatedBy]
    created_at: Mapped[CreatedAt]
    request_hash: Mapped[str]
