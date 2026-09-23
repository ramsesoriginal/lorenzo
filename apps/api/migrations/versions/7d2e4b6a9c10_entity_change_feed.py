"""player-facing change feed

Revision ID: 7d2e4b6a9c10
Revises: 4f1c9a7b2d3e
Create Date: 2026-09-23 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d2e4b6a9c10"
down_revision: str | None = "4f1c9a7b2d3e"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity_change",
        # No server defaults for id/occurred_at on purpose (ADR 0099): the app
        # supplies both so an INSERT never needs RETURNING.
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("character_entity_id", sa.UUID(), nullable=False),
        # Not a foreign key: a "deleted" row must outlive its item.
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("entity_name", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_visible", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_entity_change_tenant_id"), "entity_change", ["tenant_id"])
    # The feed's one read path: a user's rows, newest first.
    op.create_index("ix_entity_change_user_occurred", "entity_change", ["user_id", "occurred_at"])

    op.execute("ALTER TABLE entity_change ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE entity_change FORCE ROW LEVEL SECURITY")
    recipient = "user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
    tenant = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    # Readable and deletable only by the recipient - stricter than
    # notification, which also admits anyone holding the tenant context.
    op.execute(f"CREATE POLICY entity_change_read ON entity_change FOR SELECT USING ({recipient})")
    op.execute(
        f"CREATE POLICY entity_change_delete ON entity_change FOR DELETE USING ({recipient})"
    )
    # Written by whoever made the change, inside that route's tenant context.
    op.execute(
        f"CREATE POLICY entity_change_insert ON entity_change FOR INSERT WITH CHECK ({tenant})"
    )


def downgrade() -> None:
    op.drop_table("entity_change")
