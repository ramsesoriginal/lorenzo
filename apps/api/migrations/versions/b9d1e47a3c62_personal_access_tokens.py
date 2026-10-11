"""personal access tokens and their device authorizations (ADR 0268)

personal_access_token: a user's own long-lived API credential, held as a hash (SHA-256 of a
high-entropy secret shown once). device_authorization: a pending device-code approval (RFC 8628
shape). Both belong to a user, not a tenant, so neither has tenant_id or row-level security -
the same footing as app_user and user_profile_picture. The bearer lookup that resolves a token
runs before any identity is known, so there is no app.user_id for a policy to key on.

app_user.last_seen_roles remembers the Authgear roles on the user's latest interactive token, so
a personal token can carry the tenant-creator capability the user had when they last signed in.

Revision ID: b9d1e47a3c62
Revises: d7a3f1b9c2e4
Create Date: 2026-10-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9d1e47a3c62"
down_revision: str | None = "d7a3f1b9c2e4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column(
            "last_seen_roles",
            sa.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.create_table(
        "personal_access_token",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("token_hint", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="ck_pat_name_length"),
    )
    op.create_index(op.f("ix_personal_access_token_user_id"), "personal_access_token", ["user_id"])
    op.create_table(
        "device_authorization",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("device_code_hash", sa.Text(), nullable=False),
        sa.Column("user_code", sa.Text(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("token_name", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("device_code_hash"),
        sa.UniqueConstraint("user_code"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'denied')", name="ck_device_authorization_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("device_authorization")
    op.drop_table("personal_access_token")
    op.drop_column("app_user", "last_seen_roles")
