"""create containment table

Revision ID: e666b3c5be95
Revises: 8fd1b287598a
Create Date: 2026-09-08 16:58:38.082460

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e666b3c5be95"
down_revision: str | None = "8fd1b287598a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "containment",
        sa.Column("child_entity_id", sa.UUID(), nullable=False),
        sa.Column("parent_entity_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["child_entity_id"], ["entity.id"]),
        sa.ForeignKeyConstraint(["parent_entity_id"], ["entity.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("child_entity_id"),
    )
    op.create_index(
        op.f("ix_containment_parent_entity_id"), "containment", ["parent_entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_containment_tenant_id"), "containment", ["tenant_id"], unique=False
    )

    # See ADR 0012 for why both ENABLE and FORCE are needed, and ADR 0002 for
    # the currently-unenforced-in-practice caveat (the app's own DB role is a
    # superuser, which bypasses RLS unconditionally, independent of this
    # policy being correct).
    op.execute("ALTER TABLE containment ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE containment FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON containment "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    # No CHECK, no trigger - see ADR 0016: unlike entity_prototype,
    # containment is deliberately cycle-tolerant, including the trivial
    # direct self-loop case.


def downgrade() -> None:
    op.drop_index(op.f("ix_containment_tenant_id"), table_name="containment")
    op.drop_index(op.f("ix_containment_parent_entity_id"), table_name="containment")
    op.drop_table("containment")
