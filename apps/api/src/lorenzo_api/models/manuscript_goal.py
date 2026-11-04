"""An author's optional manuscript length target (ADR 0383)."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class ManuscriptGoal(Base):
    __tablename__ = "manuscript_goal"
    __table_args__ = (
        same_tenant_fk("manuscript_goal_entry_fkey", ["entry_id"], "entity", ondelete="CASCADE"),
        CheckConstraint("scope IN ('direct', 'assembled')", name="manuscript_goal_scope"),
        CheckConstraint("target_words BETWEEN 1 AND 100000000", name="manuscript_goal_target"),
        CheckConstraint("version >= 1", name="manuscript_goal_version"),
    )
    tenant_id: Mapped[TenantFk]
    entry_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(primary_key=True)
    target_words: Mapped[int | None]
    version: Mapped[int]
