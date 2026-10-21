"""Authored narrative references, independent of learning or causal order (ADR 0317)."""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class SceneFact(Base):
    __tablename__ = "scene_fact"
    __table_args__ = (
        same_tenant_fk(
            "scene_fact_source_fkey",
            ["scene_entity_id"],
            "scene",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "scene_fact_target_fkey",
            ["fact_entity_id"],
            "fact",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    scene_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    fact_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))


class SceneEvent(Base):
    __tablename__ = "scene_event"
    __table_args__ = (
        same_tenant_fk(
            "scene_event_source_fkey",
            ["scene_entity_id"],
            "scene",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "scene_event_target_fkey",
            ["event_entity_id"],
            "story_event",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    scene_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    event_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))


class SceneBeing(Base):
    __tablename__ = "scene_being"
    __table_args__ = (
        same_tenant_fk(
            "scene_being_source_fkey",
            ["scene_entity_id"],
            "scene",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "scene_being_target_fkey",
            ["being_entity_id"],
            "being",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    scene_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    being_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))


class SessionFact(Base):
    __tablename__ = "session_fact"
    __table_args__ = (
        same_tenant_fk(
            "session_fact_source_fkey",
            ["session_entity_id"],
            "story_session",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "session_fact_target_fkey",
            ["fact_entity_id"],
            "fact",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    session_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    fact_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))


class SessionEvent(Base):
    __tablename__ = "session_event"
    __table_args__ = (
        same_tenant_fk(
            "session_event_source_fkey",
            ["session_entity_id"],
            "story_session",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "session_event_target_fkey",
            ["event_entity_id"],
            "story_event",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    session_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    event_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))
