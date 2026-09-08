"""create entity table

Revision ID: 8642a27f646b
Revises:
Create Date: 2026-09-08 15:27:27.467943

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8642a27f646b"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_entity_tenant_id"), "entity", ["tenant_id"], unique=False)

    # No FK on tenant_id yet - tenant lives on the feat/auth-users branch, added once
    # both branches integrate. RLS is real regardless: see ADR 0012 for why both
    # ENABLE and FORCE are needed, and ADR 0002 for the currently-unenforced-in-
    # practice caveat (the app's own DB role is a superuser, which bypasses RLS
    # unconditionally, independent of this policy being correct).
    op.execute("ALTER TABLE entity ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE entity FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON entity "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_entity_tenant_id"), table_name="entity")
    op.drop_table("entity")
