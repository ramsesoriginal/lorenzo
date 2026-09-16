"""add tenant created_at updated_at created_by updated_by

Revision ID: 9ab3234c417c
Revises: fae51f1f72bc
Create Date: 2026-09-15 10:37:38.488566

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9ab3234c417c"
down_revision: str | None = "fae51f1f72bc"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # tenant never picked up created_at/updated_at when every other table
    # got them (ADR 0018) - its original bootstrap (ADR 0013) predates that
    # becoming a uniform convention, and nothing needed either column until
    # now: If-Match's etag_for needs updated_at, and POST/PATCH /tenants
    # (ADR 0033/RFC 0012) need created_by/updated_by. All four land together
    # here, in the same migration that gives `tenant` its first real write
    # path - not a separate backfill migration - since a handful of
    # pre-release rows are the realistic case (mirrors
    # 28b5b7c7772b_tenant_campaign_read_api_schema's own precedent for
    # campaign.slug/description).
    op.add_column(
        "tenant",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "tenant",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ADR 0029's attribution pair - nullable (an attribution can become
    # unknown, a timestamp never can), ON DELETE SET NULL (losing the
    # attributed user's account clears attribution, doesn't touch the
    # tenant it was left on). Same shape as entity's own pair
    # (26328784d301_add_entity_created_by_and_updated_by).
    op.add_column("tenant", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.add_column("tenant", sa.Column("updated_by", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_tenant_created_by"), "tenant", ["created_by"], unique=False)
    op.create_index(op.f("ix_tenant_updated_by"), "tenant", ["updated_by"], unique=False)
    op.create_foreign_key(
        "tenant_created_by_fkey", "tenant", "app_user", ["created_by"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "tenant_updated_by_fkey", "tenant", "app_user", ["updated_by"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("tenant_updated_by_fkey", "tenant", type_="foreignkey")
    op.drop_constraint("tenant_created_by_fkey", "tenant", type_="foreignkey")
    op.drop_index(op.f("ix_tenant_updated_by"), table_name="tenant")
    op.drop_index(op.f("ix_tenant_created_by"), table_name="tenant")
    op.drop_column("tenant", "updated_by")
    op.drop_column("tenant", "created_by")
    op.drop_column("tenant", "updated_at")
    op.drop_column("tenant", "created_at")
