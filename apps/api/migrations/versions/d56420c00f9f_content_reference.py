"""content_reference: the references in description text (ADR 0110)

Revision ID: d56420c00f9f
Revises: 22b8aef660db
Create Date: 2026-09-25 01:16:12.655256

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d56420c00f9f"
down_revision: str | None = "22b8aef660db"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_reference",
        sa.Column("payload_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("hint", sa.Text(), server_default="", nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('entity', 'image', 'date', 'calendar')", name="content_reference_kind"
        ),
        sa.ForeignKeyConstraint(["payload_id"], ["payload.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("payload_id", "position"),
    )
    op.create_index(
        "ix_content_reference_entity_target",
        "content_reference",
        ["tenant_id", "target"],
        unique=False,
        postgresql_where=sa.text("kind IN ('entity', 'image')"),
    )
    op.create_index(
        op.f("ix_content_reference_tenant_id"), "content_reference", ["tenant_id"], unique=False
    )
    # ADR 0002/0012: ENABLE and FORCE both, so the table owner is bound too.
    op.execute("ALTER TABLE content_reference ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE content_reference FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON content_reference "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )
    # No backfill (ADR 0110): no LorenzoScript text predates this, and a
    # description gets its rows the next time it's saved.


def downgrade() -> None:
    op.drop_table("content_reference")
