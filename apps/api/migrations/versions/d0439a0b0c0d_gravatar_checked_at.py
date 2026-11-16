"""The one-time Gravatar copy asks once per account (ADR 0439)

`app_user.gravatar_checked_at` records that the question was answered. It is set to now for every
account that exists when this runs: those accounts are never looked up, so nobody who signed up
before the policy that describes the lookup is sent to Gravatar. Only an account created later
is asked, when its email is first cached.

Revision ID: d0439a0b0c0d
Revises: c04360000001
Create Date: 2026-11-07 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0439a0b0c0d"
down_revision: str | None = "c04360000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_user", sa.Column("gravatar_checked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE app_user SET gravatar_checked_at = now()")


def downgrade() -> None:
    op.drop_column("app_user", "gravatar_checked_at")
