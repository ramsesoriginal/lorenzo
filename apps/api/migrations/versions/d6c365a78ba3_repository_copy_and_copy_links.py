"""repository_copy and the copy links: what a repository copy produced (ADR 0119)

repository_copy records that a tenant copied a repository, and when it
last synced. The three copy-link tables record, per copied entity, stat
group, and stat definition, which origin row it came from and a snapshot
of what was copied - what ADR 0121 diffs updates against.

All four belong to the copying tenant (tenant_isolation), and are
readable through the gated repository read too (ADR 0118), because a
bridge's subscribers need to read a bridge's links (ADR 0120). The source
side is a plain id, never a foreign key: it's another tenant's row, and
may disappear. The local side is a composite same-tenant key (ADR 0117)
that turns null when the local row is deleted, so a deleted copy can be
told from a row new upstream.

Revision ID: d6c365a78ba3
Revises: 256f70954d9a
Create Date: 2026-09-25 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d6c365a78ba3"
down_revision: str | None = "256f70954d9a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"

# (link table, local column, local table, whether it carries `mode`)
_LINKS = [
    ("repository_copy_link_entity", "entity_id", "entity", False),
    ("repository_copy_link_stat_group", "stat_group_id", "stat_group", True),
    ("repository_copy_link_stat_definition", "stat_definition_id", "stat_definition", True),
]


def _now(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _protect(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = {_TENANT})")
    op.execute(
        f"CREATE POLICY repository_read ON {table} FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )


def upgrade() -> None:
    op.create_table(
        "repository_copy",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("repository_tenant_id", sa.UUID(), nullable=False),
        _now("copied_at"),
        sa.Column("copied_by", sa.UUID(), nullable=True),
        _now("synced_at"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["copied_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("tenant_id", "repository_tenant_id"),
    )
    op.create_index("ix_repository_copy_copied_by", "repository_copy", ["copied_by"])
    _protect("repository_copy")

    for table, local, local_table, has_mode in _LINKS:
        columns: list[sa.Column | sa.Constraint] = [
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column(local, sa.UUID(), nullable=True),
            sa.Column("source_tenant_id", sa.UUID(), nullable=False),
            sa.Column("source_id", sa.UUID(), nullable=False),
            sa.Column("snapshot", postgresql.JSONB(), nullable=False),
            _now("copied_at"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("tenant_id", "source_id"),
        ]
        if has_mode:
            columns.append(sa.Column("mode", sa.Text(), nullable=False))
            columns.append(sa.CheckConstraint("mode IN ('copied', 'merged')", name=f"{table}_mode"))
        op.create_table(table, *columns)
        # Composite and same-tenant (ADR 0117); nulls only the local id when
        # the local row goes (PostgreSQL 15+).
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
    op.drop_table("repository_copy")
