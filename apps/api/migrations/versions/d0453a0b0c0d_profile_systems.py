"""repository_profile.systems: the game systems the current release carries (ADR 0453)

The slugs of the systems the stat groups of the current release belong to, written with the
other listing facts when a release is published or made current. Discover offers them as a facet
and filter beside the free-text `system`. Existing repositories have none until their next
release or until a release is made current again.

Revision ID: d0453a0b0c0d
Revises: d0452a0b0c0d
Create Date: 2026-11-12 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0453a0b0c0d"
down_revision: str | None = "d0452a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repository_profile",
        sa.Column(
            "systems",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("repository_profile", "systems")
