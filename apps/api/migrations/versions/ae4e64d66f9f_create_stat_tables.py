"""create stat tables

Revision ID: ae4e64d66f9f
Revises: 8642a27f646b
Create Date: 2026-09-08 16:20:01.702982

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ae4e64d66f9f"
down_revision: str | None = "8642a27f646b"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT_SCOPED_TABLES = ("stat_group", "entity_stat_group", "stat_definition", "entity_stat")


def _enable_rls(table: str) -> None:
    # See ADR 0012 for why both ENABLE and FORCE are needed, and ADR 0002 for
    # the currently-unenforced-in-practice caveat (the app's own DB role is a
    # superuser, which bypasses RLS unconditionally, independent of this
    # policy being correct).
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "stat_group",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name"),
    )
    op.create_index(op.f("ix_stat_group_tenant_id"), "stat_group", ["tenant_id"], unique=False)

    op.create_table(
        "entity_stat_group",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_group_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"]),
        sa.ForeignKeyConstraint(["stat_group_id"], ["stat_group.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("entity_id", "stat_group_id"),
    )
    op.create_index(
        op.f("ix_entity_stat_group_tenant_id"), "entity_stat_group", ["tenant_id"], unique=False
    )

    op.create_table(
        "stat_definition",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("stat_group_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "value_type",
            sa.Enum("int", "text", "float", "bool", name="stat_value_type"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["stat_group_id"], ["stat_group.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name"),
    )
    op.create_index(
        op.f("ix_stat_definition_stat_group_id"), "stat_definition", ["stat_group_id"], unique=False
    )
    op.create_index(
        op.f("ix_stat_definition_tenant_id"), "stat_definition", ["tenant_id"], unique=False
    )

    op.create_table(
        "entity_stat",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("value_int", sa.Integer(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_float", sa.Float(), nullable=True),
        sa.Column("value_bool", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "num_nonnulls(value_int, value_text, value_float, value_bool) = 1",
            name="entity_stat_exactly_one_value",
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"]),
        sa.ForeignKeyConstraint(["stat_definition_id"], ["stat_definition.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("entity_id", "stat_definition_id"),
    )
    op.create_index(op.f("ix_entity_stat_tenant_id"), "entity_stat", ["tenant_id"], unique=False)

    for table in _TENANT_SCOPED_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(op.f("ix_entity_stat_tenant_id"), table_name="entity_stat")
    op.drop_table("entity_stat")
    op.drop_index(op.f("ix_stat_definition_tenant_id"), table_name="stat_definition")
    op.drop_index(op.f("ix_stat_definition_stat_group_id"), table_name="stat_definition")
    op.drop_table("stat_definition")
    op.drop_index(op.f("ix_entity_stat_group_tenant_id"), table_name="entity_stat_group")
    op.drop_table("entity_stat_group")
    op.drop_index(op.f("ix_stat_group_tenant_id"), table_name="stat_group")
    op.drop_table("stat_group")
    # Confirmed the hard way: dropping stat_definition does NOT drop the
    # native enum type it used - CREATE TYPE isn't tied to the column's
    # lifetime the way a serial column's sequence is. Without this, a
    # subsequent upgrade fails with "type stat_value_type already exists".
    sa.Enum(name="stat_value_type").drop(op.get_bind(), checkfirst=True)
