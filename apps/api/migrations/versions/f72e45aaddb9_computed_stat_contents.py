"""computed_stat_contents: the contents formula kind (ADR 0127)

`Σ stat × quantity` over what's directly inside the entity. The kind row is
keyed and cascades like computed_stat_linear; its source stat doesn't
cascade (NO ACTION), like every other formula input (ADR 0104). Every key
between tenant tables is composite with tenant_id (ADR 0117), and it's
repository content (ADR 0118): tenant_isolation, repository_read, and FORCE
ROW LEVEL SECURITY.

Revision ID: f72e45aaddb9
Revises: 1e0ae40cab18
Create Date: 2026-09-27 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f72e45aaddb9"
down_revision: str | None = "1e0ae40cab18"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLE = "computed_stat_contents"
_TENANT = "current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source_stat_definition_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
        sa.ForeignKeyConstraint(
            ["entity_id", "stat_definition_id", "tenant_id"],
            [
                "computed_stat.entity_id",
                "computed_stat.stat_definition_id",
                "computed_stat.tenant_id",
            ],
            name=f"{_TABLE}_entity_id_stat_definition_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_stat_definition_id", "tenant_id"],
            ["stat_definition.id", "stat_definition.tenant_id"],
            name=f"{_TABLE}_source_stat_definition_id_fkey",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    op.create_index(f"ix_{_TABLE}_tenant_id", _TABLE, ["tenant_id"])
    # The reverse-dependency lookup (ADR 0104) reads by source stat.
    op.create_index(f"ix_{_TABLE}_source_stat_definition_id", _TABLE, ["source_stat_definition_id"])
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON {_TABLE} USING (tenant_id = {_TENANT})")
    op.execute(
        f"CREATE POLICY repository_read ON {_TABLE} FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
