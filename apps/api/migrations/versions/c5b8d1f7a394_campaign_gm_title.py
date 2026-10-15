"""a campaign's name for its game master (ADR 0294)

`campaign.gm_title` and `campaign.gm_title_plural`: what a table calls its game master, a label
and not a role (RFC 0040 section 4). Both null while the campaign keeps the default, "GM" and
"GMs", which the API fills in on every read. Written together or not at all. The table keeps its
policies; nothing else changes.

Revision ID: c5b8d1f7a394
Revises: a7d4e9c1f263
Create Date: 2026-10-15 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5b8d1f7a394"
down_revision: str | None = "a7d4e9c1f263"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaign", sa.Column("gm_title", sa.String(), nullable=True))
    op.add_column("campaign", sa.Column("gm_title_plural", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("campaign", "gm_title_plural")
    op.drop_column("campaign", "gm_title")
