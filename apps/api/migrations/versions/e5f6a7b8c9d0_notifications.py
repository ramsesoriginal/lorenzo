"""notifications

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-17 10:47:39.001095

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        # Nullable - null for platform scope, where no single tenant applies.
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_notification_user_id"), "notification", ["user_id"], unique=False)
    op.create_index(op.f("ix_notification_tenant_id"), "notification", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_notification_created_by"), "notification", ["created_by"], unique=False
    )

    # ADR 0054: split by command, unlike every other RLS'd table so far.
    #
    # SELECT/UPDATE extend the self-access-OR-tenant-scoped shape
    # migrations/versions/a22dc991a926_*.py already proved out for
    # player/campaign_gm with a third clause, created_by = app.user_id.
    # GET /me/notifications needs to read a caller's own rows across every
    # tenant (and platform-scoped rows, which have no tenant_id at all)
    # with only app.user_id set, no per-tenant looping - that's the first
    # two clauses. The third exists purely because of a genuine Postgres
    # RLS wrinkle, confirmed the hard way: `INSERT ... RETURNING` (which
    # SQLAlchemy's ORM always uses, to read the server-generated id/
    # created_at back onto the new object) re-checks the just-inserted row
    # against the table's own SELECT policy, raising the exact same
    # "violates row-level security policy" error if it doesn't satisfy it -
    # even though the INSERT's own WITH CHECK already passed. A platform
    # notification (no tenant_id, written by a platform operator *for* a
    # different recipient) satisfied neither of the first two clauses, so
    # every platform-scope creation failed on the RETURNING step alone.
    # Since every notification's `created_by` is always the caller
    # authorized to create it (get_tenant_context/can_manage_campaign/
    # _authorize_rename/require_platform_operator_role, one gate per
    # scope), letting a caller also read back what they themselves just
    # created is a harmless, narrow extension - not a new way to read
    # someone else's notifications after the fact, since this only matches
    # while app.user_id still equals that same created_by value.
    #
    # INSERT itself stays permissive (WITH CHECK (true)): the row's own
    # user_id (the recipient) is essentially never app.user_id (the
    # actor), so the INSERT-time check can't reasonably key off it either;
    # authorization for *who* may create a notification is fully handled
    # at the API layer instead, matching this schema's own standing
    # "defense in depth for a missed filter, not a replacement for
    # filtering deliberately" principle (ADR 0002).
    op.execute("ALTER TABLE notification ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification FORCE ROW LEVEL SECURITY")
    _read_using = (
        "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid "
        "OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid "
        "OR created_by = NULLIF(current_setting('app.user_id', true), '')::uuid"
    )
    op.execute(f"CREATE POLICY notification_read ON notification FOR SELECT USING ({_read_using})")
    op.execute(
        "CREATE POLICY notification_update ON notification FOR UPDATE "
        f"USING ({_read_using}) WITH CHECK ({_read_using})"
    )
    op.execute("CREATE POLICY notification_insert ON notification FOR INSERT WITH CHECK (true)")


def downgrade() -> None:
    op.drop_table("notification")
