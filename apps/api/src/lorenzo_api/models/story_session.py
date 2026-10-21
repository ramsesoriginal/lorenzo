"""Session planning and reusable narrative Scenes (ADR 0317)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class Scene(Base):
    __tablename__ = "scene"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="scene_tenant_key"),
        same_tenant_fk("scene_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "scene_period_fkey",
            ["period_entity_id"],
            "calendar_period",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    period_entity_id: Mapped[uuid.UUID | None]


class StorySession(Base):
    __tablename__ = "story_session"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="story_session_tenant_key"),
        UniqueConstraint(
            "entity_id", "campaign_id", "tenant_id", name="story_session_campaign_key"
        ),
        same_tenant_fk("story_session_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "story_session_campaign_fkey", ["campaign_id"], "campaign", ondelete="NO ACTION"
        ),
        same_tenant_fk(
            "story_session_start_fkey",
            ["start_period_id"],
            "calendar_period",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    campaign_id: Mapped[uuid.UUID]
    real_date: Mapped[date | None]
    start_period_id: Mapped[uuid.UUID | None]


class SessionGm(Base):
    __tablename__ = "session_gm"
    __table_args__ = (
        same_tenant_fk(
            "session_gm_session_fkey",
            ["session_entity_id"],
            "story_session",
            ["entity_id"],
            ondelete="CASCADE",
        ),
    )
    session_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]


class SessionPlayer(Base):
    __tablename__ = "session_player"
    __table_args__ = (
        UniqueConstraint(
            "session_entity_id", "player_id", "tenant_id", name="session_player_tenant_key"
        ),
        same_tenant_fk(
            "session_player_session_fkey",
            ["session_entity_id", "campaign_id"],
            "story_session",
            ["entity_id", "campaign_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "session_player_player_fkey",
            ["player_id", "campaign_id"],
            "player",
            ["id", "campaign_id"],
            ondelete="CASCADE",
        ),
    )
    session_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    player_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    campaign_id: Mapped[uuid.UUID]


class SessionCharacter(Base):
    __tablename__ = "session_character"
    __table_args__ = (
        same_tenant_fk(
            "session_character_attendee_fkey",
            ["session_entity_id", "player_id"],
            "session_player",
            ["session_entity_id", "player_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "session_character_character_fkey",
            ["character_entity_id", "player_id"],
            "character_player",
            ["character_entity_id", "player_id"],
            ondelete="CASCADE",
        ),
    )
    session_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    player_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    character_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]


class SceneAppearance(Base):
    __tablename__ = "scene_appearance"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="scene_appearance_tenant_key"),
        UniqueConstraint(
            "session_entity_id",
            "position",
            name="scene_appearance_position_key",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="scene_appearance_position"),
        CheckConstraint(
            "play_status IN ('planned', 'played', 'skipped')", name="scene_appearance_play_status"
        ),
        CheckConstraint(
            "(play_status = 'played') = (played_position IS NOT NULL)",
            name="scene_appearance_play_shape",
        ),
        CheckConstraint(
            "played_position IS NULL OR played_position >= 0",
            name="scene_appearance_played_position",
        ),
        UniqueConstraint(
            "session_entity_id",
            "played_position",
            name="scene_appearance_played_position_key",
            deferrable=True,
            initially="DEFERRED",
        ),
        same_tenant_fk("scene_appearance_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "scene_appearance_session_fkey",
            ["session_entity_id"],
            "story_session",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
        same_tenant_fk(
            "scene_appearance_scene_fkey",
            ["scene_entity_id"],
            "scene",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    session_entity_id: Mapped[uuid.UUID]
    scene_entity_id: Mapped[uuid.UUID]
    position: Mapped[int]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))
    play_status: Mapped[str] = mapped_column(server_default="planned")
    played_position: Mapped[int | None]
