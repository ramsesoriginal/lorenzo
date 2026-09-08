"""add file_type to payload_document

Revision ID: 65ef08962fe4
Revises: 6c2f0a9d3e17
Create Date: 2026-09-08 21:30:01.426785

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "65ef08962fe4"
down_revision: str | None = "6c2f0a9d3e17"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payload_document", sa.Column("file_type", sa.Text(), nullable=False))


def downgrade() -> None:
    op.drop_column("payload_document", "file_type")
