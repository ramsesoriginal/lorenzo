"""user, tenant name, membership

Revision ID: 8b1772ba94a9
Revises: 8aced4b80842
Create Date: 2026-09-09 00:40:43.973022

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8b1772ba94a9"
down_revision: str | None = "8aced4b80842"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_MEMBERSHIP_ROLE = sa.Enum("owner", "orga", name="membership_role")


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("name", sa.Text(), server_default=sa.text("'Unnamed Tenant'"), nullable=False),
    )

    # app_user has no tenant_id - a User is a global identity, not scoped to
    # any single tenant (ADR 0010/0022) - so no RLS here at all.
    op.create_table(
        "app_user",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("authgear_subject_id", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("authgear_subject_id"),
    )

    # create_table() below auto-creates the enum type for its Enum-typed
    # column - no separate explicit .create() call (that double-creates it
    # within the same transaction and fails with DuplicateObjectError,
    # confirmed the hard way). Only downgrade needs an explicit .drop() -
    # drop_table doesn't clean up the enum type on its own.
    op.create_table(
        "membership",
        # tenant_id leads the composite PK (not user_id) - RLS filters every
        # query by tenant_id, so the PK's own index serves that access
        # pattern for free as its leading column. See ADR 0022.
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", _MEMBERSHIP_ROLE, nullable=False),
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
        sa.PrimaryKeyConstraint("tenant_id", "user_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
    )

    # See ADR 0021 - this role already has blanket SELECT/INSERT/UPDATE/
    # DELETE + future-table coverage via ALTER DEFAULT PRIVILEGES, so no
    # additional GRANT is needed for either new table here.
    op.execute("ALTER TABLE membership ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE membership FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON membership "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.drop_table("membership")
    _MEMBERSHIP_ROLE.drop(op.get_bind(), checkfirst=True)
    op.drop_table("app_user")
    op.drop_column("tenant", "name")
