"""Book identity and independently composed Editions and Chapters (ADR 0341)."""

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class Book(Base):
    __tablename__ = "book"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="book_tenant_key"),
        same_tenant_fk("book_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]


class Edition(Base):
    __tablename__ = "edition"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="edition_tenant_key"),
        same_tenant_fk("edition_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "edition_book_fkey", ["book_entity_id"], "book", ["entity_id"], ondelete="NO ACTION"
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    book_entity_id: Mapped[uuid.UUID]


class Chapter(Base):
    __tablename__ = "chapter"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="chapter_tenant_key"),
        same_tenant_fk("chapter_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]


class ManuscriptPlacement(Base):
    __tablename__ = "manuscript_placement"
    __table_args__ = (
        CheckConstraint(
            "parent_entity_id <> chapter_entity_id", name="manuscript_placement_not_self"
        ),
        same_tenant_fk(
            "manuscript_placement_parent_fkey", ["parent_entity_id"], "entity", ondelete="NO ACTION"
        ),
        same_tenant_fk(
            "manuscript_placement_chapter_fkey",
            ["chapter_entity_id"],
            "chapter",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "manuscript_placement_payload_fkey",
            ["before_payload_id"],
            "payload",
            ondelete="NO ACTION",
        ),
    )
    chapter_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    parent_entity_id: Mapped[uuid.UUID]
    before_payload_id: Mapped[uuid.UUID | None]
    position: Mapped[int]
