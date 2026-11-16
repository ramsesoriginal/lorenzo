"""repository_copy_link_system and repository_copy_link_template (ADR 0469)

The copy links of a game system and of a template, so the update engine can track them as it does
a stat group: where the library's row came from, and a snapshot of what was copied, with every id
translated to its origin. The local id is null once the local row is deleted (ON DELETE SET NULL
of that column only, PostgreSQL 15+). Copy bookkeeping is the library's, not the repository's:
tenant isolation and the repository read policy as every link table has, and FORCE ROW LEVEL
SECURITY. A copy made before this has no links: the update engine offers the repository's system
and templates as additions, and the system it already has is joined by slug.

Revision ID: d0462a0b0c0d
Revises: d0461a0b0c0d
Create Date: 2026-11-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0462a0b0c0d"
down_revision: str | None = "d0461a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"
# (table, local id column, the table it points to, has a mode)
_LINKS = [
    ("repository_copy_link_system", "system_id", "system", True),
    ("repository_copy_link_template", "template_id", "template", False),
]


def _protect(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = {_TENANT})")
    op.execute(
        f"CREATE POLICY repository_read ON {table} FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )


def upgrade() -> None:
    for table, local, local_table, has_mode in _LINKS:
        columns: list[sa.Column | sa.Constraint] = [
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column(local, sa.UUID(), nullable=True),
            sa.Column("source_tenant_id", sa.UUID(), nullable=False),
            sa.Column("source_id", sa.UUID(), nullable=False),
            sa.Column("snapshot", postgresql.JSONB(), nullable=False),
            sa.Column(
                "copied_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("tenant_id", "source_id"),
        ]
        if has_mode:
            columns.append(sa.Column("mode", sa.Text(), nullable=False))
            columns.append(sa.CheckConstraint("mode IN ('copied', 'merged')", name=f"{table}_mode"))
        op.create_table(table, *columns)
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_{local}_fkey "
            f"FOREIGN KEY ({local}, tenant_id) REFERENCES {local_table} (id, tenant_id) "
            f"ON DELETE SET NULL ({local})"
        )
        op.create_index(f"ix_{table}_{local}", table, [local])
        op.create_index(f"ix_{table}_source_tenant_id", table, ["tenant_id", "source_tenant_id"])
        _protect(table)


def downgrade() -> None:
    for table, _, _, _ in reversed(_LINKS):
        op.drop_table(table)
