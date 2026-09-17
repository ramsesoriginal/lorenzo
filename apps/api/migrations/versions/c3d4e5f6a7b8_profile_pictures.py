"""profile pictures

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-17 09:00:32.571410

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def upgrade() -> None:
    # No tenant_id, no RLS (ADR 0052) - a row here can belong to a User
    # (global, no tenant) or a Tenant/Campaign (tenant-scoped), and there is
    # no single RLS predicate that correctly covers both. Real isolation
    # lives on the three link tables below.
    op.create_table(
        "profile_picture",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # user_profile_picture: no tenant_id/RLS, matching app_user's own
    # global-identity precedent (ADR 0022).
    op.create_table(
        "user_profile_picture",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("profile_picture_id", sa.UUID(), nullable=False, unique=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_picture_id"], ["profile_picture.id"], ondelete="CASCADE"),
    )

    # tenant_profile_picture and campaign_profile_picture: RLS'd, same
    # tenant_isolation shape every RLS'd table in this schema already uses.
    op.create_table(
        "tenant_profile_picture",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("profile_picture_id", sa.UUID(), nullable=False, unique=True),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_picture_id"], ["profile_picture.id"], ondelete="CASCADE"),
    )
    _enable_rls("tenant_profile_picture")

    op.create_table(
        "campaign_profile_picture",
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        # Denormalized copy of campaign.tenant_id (RLS only) - same pattern
        # player/campaign_gm already use for their own tenant_id column.
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("profile_picture_id", sa.UUID(), nullable=False, unique=True),
        sa.PrimaryKeyConstraint("campaign_id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_picture_id"], ["profile_picture.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_campaign_profile_picture_tenant_id", "campaign_profile_picture", ["tenant_id"]
    )
    _enable_rls("campaign_profile_picture")


def downgrade() -> None:
    op.drop_table("campaign_profile_picture")
    op.drop_table("tenant_profile_picture")
    op.drop_table("user_profile_picture")
    op.drop_table("profile_picture")
