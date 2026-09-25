from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.payload import Payload


class ContentReference(Base):
    """One reference in a description's LorenzoScript text - see ADR 0110:
    an entity link, entity picture, date, or calendar expression, in order
    of first use. Derived: description_payloads.write_description replaces a
    payload's rows whenever its text changes, and nothing else writes them.

    An entity reference keeps the slug as written in `target` rather than an
    entity id, so it resolves through entity_slug when read, the way
    rendering does. A slug set later makes an old link count.
    """

    __tablename__ = "content_reference"
    __table_args__ = (
        same_tenant_fk(
            "content_reference_payload_id_fkey", ["payload_id"], "payload", ondelete="CASCADE"
        ),
        CheckConstraint(
            "kind IN ('entity', 'image', 'date', 'calendar')", name="content_reference_kind"
        ),
        # Backlinks: which texts name this slug.
        Index(
            "ix_content_reference_entity_target",
            "tenant_id",
            "target",
            postgresql_where=text("kind IN ('entity', 'image')"),
        ),
    )

    payload_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    kind: Mapped[str]
    # The view hint of an entity or image reference; '' for the other kinds.
    hint: Mapped[str] = mapped_column(server_default="")
    # The slug, the ISO date (text order is date order), or the expression.
    target: Mapped[str]

    payload: Mapped[Payload] = relationship(
        foreign_keys="ContentReference.payload_id", lazy="raise_on_sql"
    )
