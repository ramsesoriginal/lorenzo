"""the author role (ADR 0219)

One enum value and nothing that uses it: a value added to a native enum cannot be used in
the transaction that adds it, and no check, policy or backfill names it. Postgres cannot
remove an enum value, so the downgrade leaves it in place.

Revision ID: a3c81d6e0f52
Revises: f9b3d6e8a2c4
Create Date: 2026-10-08 17:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3c81d6e0f52"
down_revision: str | None = "a4d1c7e90b36"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE membership_role ADD VALUE IF NOT EXISTS 'author'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for an enum: the value stays.
    pass
