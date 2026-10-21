"""Fact anchors, subjects and explicit outer audiences (ADR 0305)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, UpdatedAt, UuidPk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class Fact(Base):
    __tablename__ = "fact"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="fact_entity_id_tenant_id_key"),
        same_tenant_fk("fact_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    entity: Mapped[Entity] = relationship(
        foreign_keys="Fact.entity_id", lazy="raise_on_sql", back_populates="fact"
    )


class EntityAudience(Base):
    __tablename__ = "entity_audience"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="entity_audience_entity_id_tenant_id_key"),
        same_tenant_fk(
            "entity_audience_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    is_public: Mapped[bool] = mapped_column(server_default=text("false"))
    shared_with_participants: Mapped[bool] = mapped_column(server_default=text("false"))
    updated_at: Mapped[UpdatedAt]


class EntityKnowledge(Base):
    __tablename__ = "entity_knowledge"
    __table_args__ = (
        same_tenant_fk(
            "entity_knowledge_entity_id_fkey",
            ["entity_id"],
            "entity_audience",
            target_columns=["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "entity_knowledge_knower_entity_id_fkey",
            ["knower_entity_id"],
            "entity",
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "entity_knowledge_knower_player_id_fkey",
            ["knower_player_id"],
            "player",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "num_nonnulls(knower_entity_id, knower_player_id) = 1",
            name="entity_knowledge_exactly_one_knower",
        ),
        UniqueConstraint(
            "entity_id", "knower_entity_id", name="entity_knowledge_unique_entity_knower"
        ),
        UniqueConstraint(
            "entity_id", "knower_player_id", name="entity_knowledge_unique_player_knower"
        ),
    )
    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    knower_entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    knower_player_id: Mapped[uuid.UUID | None] = mapped_column(index=True)


class FactAbout(Base):
    __tablename__ = "fact_about"
    __table_args__ = (
        same_tenant_fk(
            "fact_about_fact_entity_id_fkey",
            ["fact_entity_id"],
            "fact",
            target_columns=["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "fact_about_subject_entity_id_fkey", ["subject_entity_id"], "entity", ondelete="CASCADE"
        ),
    )
    fact_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[TenantFk]
