"""app_user email and nickname

Revision ID: b2c3d4e5f6a7
Revises: a1c2d3e4f5a6
Create Date: 2026-09-17 00:32:13.612233

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1c2d3e4f5a6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("app_user", sa.Column("nickname", sa.Text(), nullable=True))
    # Partial unique indexes, not plain UniqueConstraints - both are optional
    # (an unverified/never-logged-in user has no email yet; nickname is
    # opt-in), and app_user is a global identity with no tenant_id to scope
    # by (ADR 0022), unlike item_instance.slug's tenant-scoped precedent
    # (ADR 0043) - these are simple single-column indexes instead.
    op.create_index(
        "ix_app_user_email",
        "app_user",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "ix_app_user_nickname",
        "app_user",
        ["nickname"],
        unique=True,
        postgresql_where=sa.text("nickname IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_app_user_nickname", table_name="app_user")
    op.drop_index("ix_app_user_email", table_name="app_user")
    op.drop_column("app_user", "nickname")
    op.drop_column("app_user", "email")
