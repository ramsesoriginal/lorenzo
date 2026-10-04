"""campaign_invite.role: a GM invite link (ADR 0177)

Revision ID: b5d2c8f1a4e7
Revises: a7c3f95e2b18
Create Date: 2026-10-04 19:00:00.000000

An invite gains a role: `player` (every link ADR 0092 defined, so every existing
row) or `gm` (single use, short-lived, created only by someone who could grant GM
directly). The single-use and lifetime limits are enforced where links are
created, not by a constraint, as ADR 0092's own expiry and use limits are.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5d2c8f1a4e7"
down_revision: str | None = "a7c3f95e2b18"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_INVITE_ROLE = sa.Enum("player", "gm", name="campaign_invite_role")


def upgrade() -> None:
    _INVITE_ROLE.create(op.get_bind())
    op.add_column(
        "campaign_invite",
        sa.Column("role", _INVITE_ROLE, server_default="player", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("campaign_invite", "role")
    _INVITE_ROLE.drop(op.get_bind())
