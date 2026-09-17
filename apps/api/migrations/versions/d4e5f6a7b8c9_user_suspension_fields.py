"""user suspension fields

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-17 10:46:32.646487

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ADR 0053: nullable - most users are never suspended, and a fresh
    # auto-provisioned user is never suspended by construction. suspended_by
    # is ON DELETE SET NULL, same reasoning created_by/updated_by already
    # use elsewhere (ADR 0029) - the suspending operator's own account
    # disappearing doesn't lift the suspension, it just loses attribution.
    op.add_column("app_user", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("app_user", sa.Column("suspended_by", sa.Uuid(), nullable=True))
    op.add_column("app_user", sa.Column("suspension_reason", sa.Text(), nullable=True))
    op.create_index(op.f("ix_app_user_suspended_by"), "app_user", ["suspended_by"], unique=False)
    op.create_foreign_key(
        "app_user_suspended_by_fkey",
        "app_user",
        "app_user",
        ["suspended_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("app_user_suspended_by_fkey", "app_user", type_="foreignkey")
    op.drop_index(op.f("ix_app_user_suspended_by"), table_name="app_user")
    op.drop_column("app_user", "suspension_reason")
    op.drop_column("app_user", "suspended_by")
    op.drop_column("app_user", "suspended_at")
