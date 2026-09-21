"""campaign invite links

Revision ID: 4f1c9a7b2d3e
Revises: b8c9d0e1f2a3
Create Date: 2026-09-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4f1c9a7b2d3e"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_invite",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        # SHA-256 hex of the token, never the token itself (ADR 0092).
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # NULL = unlimited, on purpose (ADR 0092).
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("token_hash"),
        sa.CheckConstraint("max_uses IS NULL OR max_uses >= 1", name="campaign_invite_max_uses"),
    )
    op.create_index(
        op.f("ix_campaign_invite_tenant_id"), "campaign_invite", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_campaign_invite_campaign_id"), "campaign_invite", ["campaign_id"], unique=False
    )

    op.execute("ALTER TABLE campaign_invite ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE campaign_invite FORCE ROW LEVEL SECURITY")
    # NULLIF(..., '') so an unset *or* blank setting is NULL rather than an
    # "invalid input syntax for type uuid" error - notification's own shape
    # (ADR 0058). The public preview/redeem routes run with no
    # app.tenant_id at all until the token has been resolved.
    tenant_match = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    op.execute(
        "CREATE POLICY campaign_invite_tenant ON campaign_invite "
        f"USING ({tenant_match}) WITH CHECK ({tenant_match})"
    )
    # Select-only, and only ever for the one row whose hash matches: a token
    # holder can read that invite and nothing else, and can write nothing.
    op.execute(
        "CREATE POLICY campaign_invite_by_token ON campaign_invite FOR SELECT "
        "USING (token_hash = NULLIF(current_setting('app.invite_token_hash', true), ''))"
    )


def downgrade() -> None:
    op.drop_table("campaign_invite")
