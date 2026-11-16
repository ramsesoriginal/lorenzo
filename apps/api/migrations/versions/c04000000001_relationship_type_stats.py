"""The library's three relationship-type stats (ADR 0400).

A library says which stat definitions say that a type of relationship is directed, and how it
reads from either end. Each is a same-tenant composite key into stat_definition that clears only
the reference when the definition is deleted (PostgreSQL 15+), as the being stat group does.

Revision ID: c04000000001
Revises: c04030000001
Create Date: 2026-11-06 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c04000000001"
down_revision: str | None = "c04030000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_COLUMNS = (
    "relationship_directed_stat_id",
    "relationship_reads_as_stat_id",
    "relationship_reads_as_back_stat_id",
)


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column("tenant", sa.Column(column, sa.Uuid(), nullable=True))
        op.execute(
            f"ALTER TABLE tenant ADD CONSTRAINT tenant_{column}_fkey "
            f"FOREIGN KEY ({column}, id) REFERENCES stat_definition (id, tenant_id) "
            f"ON DELETE SET NULL ({column})"
        )


def downgrade() -> None:
    for column in _COLUMNS:
        op.drop_constraint(f"tenant_{column}_fkey", "tenant", type_="foreignkey")
        op.drop_column("tenant", column)
