"""A person's saved view of a list: its filters and order, by name, in one library (ADR 0532)."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk


class SavedView(Base):
    """What a person set a list to (its filters, order and the like), kept under a name. It is
    theirs alone: another member of the library never reads it. `app` and `list` say which list
    it is for; `query` is whatever that list needs to set itself the same way again."""

    __tablename__ = "saved_view"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "app", "list", "name", name="saved_view_name_key"),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    app: Mapped[str] = mapped_column(Text)
    list: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    query: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
