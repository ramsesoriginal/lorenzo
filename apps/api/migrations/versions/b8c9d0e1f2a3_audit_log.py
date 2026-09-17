"""audit log

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-17 14:12:10.150007

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # Not nullable for this first slice (ADR 0063) - platform-scope
        # events (e.g. suspension) are explicitly out of scope, not a NULL
        # case to design around yet.
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["app_user.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_audit_log_tenant_id"), "audit_log", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False)

    # Plain tenant_id-scoped RLS - the ordinary shape, no self-access clause
    # needed unlike `notification` (ADR 0058/0061): this is inherently a
    # per-tenant admin view, not a cross-tenant personal inbox.
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON audit_log "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.drop_table("audit_log")
