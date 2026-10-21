"""Operational presentation records; never Event-order evidence (ADR 0318)."""

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class SessionSequence(Base):
    __tablename__ = "session_sequence"
    __table_args__ = (
        same_tenant_fk(
            "session_sequence_session_fkey",
            ["session_entity_id", "campaign_id"],
            "story_session",
            ["entity_id", "campaign_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "campaign_id",
            "position",
            name="session_sequence_position_key",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="session_sequence_position"),
    )
    session_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    campaign_id: Mapped[uuid.UUID]
    position: Mapped[int]


class EventPresentation(Base):
    __tablename__ = "event_presentation"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="event_presentation_tenant_key"),
        same_tenant_fk(
            "event_presentation_appearance_fkey",
            ["appearance_entity_id"],
            "scene_appearance",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
        same_tenant_fk(
            "event_presentation_event_fkey",
            ["event_entity_id"],
            "story_event",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "appearance_entity_id",
            "position",
            name="event_presentation_position_key",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="event_presentation_position"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    appearance_entity_id: Mapped[uuid.UUID]
    event_entity_id: Mapped[uuid.UUID]
    position: Mapped[int]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))
