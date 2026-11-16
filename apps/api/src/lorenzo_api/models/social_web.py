"""SocialWeb: a saved view of relationships (ADR 0406). It says what it shows, not what is true."""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class SocialWeb(Base):
    """The marker that makes an entry a SocialWeb. `layout` is a name from a closed list in code;
    `view` holds visual-only switches and never an entry id. The standing and the date lens are
    the matrix's, saved with the view; a deleted stat definition or Event clears only its column."""

    __tablename__ = "social_web"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="social_web_entity_tenant_key"),
        same_tenant_fk("social_web_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "social_web_standing_stat_id_fkey",
            ["standing_stat_id"],
            "stat_definition",
            ondelete="SET NULL",
        ),
        same_tenant_fk(
            "social_web_as_of_event_fkey",
            ["as_of_event"],
            "story_event",
            ["entity_id"],
            ondelete="SET NULL",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    layout: Mapped[str]
    layout_seed: Mapped[int]
    theme_hint: Mapped[str | None]
    view: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    standing_stat_id: Mapped[uuid.UUID | None]
    as_of_event: Mapped[uuid.UUID | None]


class SocialWebEntry(Base):
    """One member of a web, and where it was put by hand. `x` and `y` are both set or both null."""

    __tablename__ = "social_web_entry"
    __table_args__ = (
        CheckConstraint("(x IS NULL) = (y IS NULL)", name="social_web_entry_position"),
        same_tenant_fk(
            "social_web_entry_web_fkey",
            ["web_entity_id"],
            "social_web",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "social_web_entry_entry_fkey", ["entry_entity_id"], "entity", ondelete="CASCADE"
        ),
    )
    web_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    entry_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    x: Mapped[float | None]
    y: Mapped[float | None]


class SocialWebType(Base):
    """A type (a prototype entry) a web limits its edges to; no rows means every type."""

    __tablename__ = "social_web_type"
    __table_args__ = (
        same_tenant_fk(
            "social_web_type_web_fkey",
            ["web_entity_id"],
            "social_web",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "social_web_type_type_fkey", ["type_entity_id"], "entity", ondelete="CASCADE"
        ),
    )
    web_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    type_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
