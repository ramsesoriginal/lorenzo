"""system: a game system a library holds the vocabulary of, and stat_group.system_id (ADR 0448)

A system is a row: a slug (a short lowercase word, the prefix of the names of its stat
definitions), a name, and an optional root entry. A stat group may belong to one. Both keys are
composite with tenant_id (ADR 0117), the root entry's SET NULL clears only that column, and the
table is repository content (ADR 0118): tenant_isolation, repository_read, and FORCE ROW LEVEL
SECURITY. A group's key to its system does not clear it: deleting a system a group has is refused
by the API.

Revision ID: d0448a0b0c0d
Revises: d0447a0b0c0d
Create Date: 2026-11-12 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0448a0b0c0d"
down_revision: str | None = "d0447a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    op.create_table(
        "system",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("root_entry_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="system_id_tenant_id_key"),
        sa.UniqueConstraint("tenant_id", "slug", name="system_tenant_id_slug_key"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint("slug ~ '^[a-z][a-z0-9]{0,31}$'", name="system_slug_is_a_short_word"),
    )
    op.execute(
        "ALTER TABLE system ADD CONSTRAINT system_root_entry_id_fkey "
        "FOREIGN KEY (root_entry_id, tenant_id) REFERENCES entity (id, tenant_id) "
        "ON DELETE SET NULL (root_entry_id)"
    )
    op.create_index("ix_system_root_entry_id", "system", ["root_entry_id"])
    op.create_index("ix_system_tenant_id", "system", ["tenant_id"])
    op.execute("ALTER TABLE system ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE system FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON system USING (tenant_id = {_TENANT})")
    op.execute(
        "CREATE POLICY repository_read ON system FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )
    op.add_column("stat_group", sa.Column("system_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "stat_group_system_id_fkey",
        "stat_group",
        "system",
        ["system_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_index("ix_stat_group_system_id", "stat_group", ["system_id"])


def downgrade() -> None:
    op.drop_index("ix_stat_group_system_id", table_name="stat_group")
    op.drop_constraint("stat_group_system_id_fkey", "stat_group", type_="foreignkey")
    op.drop_column("stat_group", "system_id")
    op.drop_table("system")
