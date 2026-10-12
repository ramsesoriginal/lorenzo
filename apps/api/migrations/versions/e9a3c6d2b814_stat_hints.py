"""stat definitions: a maximum, a minimum and a resolved-value hint (links to other definitions)

ADR 0279. Clues for a client, never limits: "of 9" beside stress, "+3" beside a score, a floor for
a stepper. Each link is composite and same-tenant (ADR 0117), and deleting the hinted definition
clears only the link (PostgreSQL 15+): a plain ON DELETE SET NULL would try to null tenant_id too.

Revision ID: e9a3c6d2b814
Revises: d1f4b7a92c36
Create Date: 2026-10-12 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9a3c6d2b814"
down_revision: str | None = "d1f4b7a92c36"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_HINTS = ("max_hint_id", "min_hint_id", "resolved_hint_id")


def upgrade() -> None:
    for column in _HINTS:
        op.add_column("stat_definition", sa.Column(column, sa.Uuid(), nullable=True))
        op.execute(
            f"ALTER TABLE stat_definition ADD CONSTRAINT stat_definition_{column}_fkey "
            f"FOREIGN KEY ({column}, tenant_id) REFERENCES stat_definition (id, tenant_id) "
            f"ON DELETE SET NULL ({column})"
        )


def downgrade() -> None:
    for column in _HINTS:
        op.execute(f"ALTER TABLE stat_definition DROP CONSTRAINT stat_definition_{column}_fkey")
        op.drop_column("stat_definition", column)
