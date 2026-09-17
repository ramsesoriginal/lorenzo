"""user profile expansion

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-17 13:58:47.399969

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ADR 0056: display_name is a friendly label, deliberately not unique -
    # nickname stays the unique lookup handle (ADR 0050/0051).
    op.add_column("app_user", sa.Column("display_name", sa.Text(), nullable=True))
    op.add_column("app_user", sa.Column("pronouns", sa.Text(), nullable=True))
    op.add_column("app_user", sa.Column("bio", sa.Text(), nullable=True))
    # This codebase's first native Postgres array column - a short,
    # homogeneous, order-not-load-bearing list of locale tags doesn't earn
    # a join table the way a genuine many-to-many domain relationship does.
    op.add_column(
        "app_user",
        sa.Column("locales", sa.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
    )
    # #RRGGBB validated at the schema boundary (schemas/users.py), not here -
    # same "format-checking is an application concern" precedent
    # PayloadDescription.locale (ADR 0017) already established.
    op.add_column("app_user", sa.Column("user_color", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("app_user", "user_color")
    op.drop_column("app_user", "locales")
    op.drop_column("app_user", "bio")
    op.drop_column("app_user", "pronouns")
    op.drop_column("app_user", "display_name")
