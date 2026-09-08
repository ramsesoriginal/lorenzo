"""create item and item_instance tables

Revision ID: 1df927764baa
Revises: f49a3c5ec028
Create Date: 2026-09-08 18:55:30.432834

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1df927764baa"
down_revision: str | None = "f49a3c5ec028"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT_SCOPED_TABLES = ("item", "item_instance")


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
        "item",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entity_id"),
    )
    op.create_index(op.f("ix_item_tenant_id"), "item", ["tenant_id"], unique=False)

    op.create_table(
        "item_instance",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("owner_entity_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_entity_id"], ["entity.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entity_id"),
    )
    op.create_index(
        op.f("ix_item_instance_owner_entity_id"), "item_instance", ["owner_entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_item_instance_tenant_id"), "item_instance", ["tenant_id"], unique=False
    )

    for table in _TENANT_SCOPED_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(op.f("ix_item_instance_tenant_id"), table_name="item_instance")
    op.drop_index(op.f("ix_item_instance_owner_entity_id"), table_name="item_instance")
    op.drop_table("item_instance")
    op.drop_index(op.f("ix_item_tenant_id"), table_name="item")
    op.drop_table("item")
