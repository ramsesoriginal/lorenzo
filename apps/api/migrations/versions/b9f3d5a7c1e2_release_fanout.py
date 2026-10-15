"""the announcement of a release is a row with a cursor (ADR 0301)

`release_fanout(id, tenant_id, release_id, type, title, body, created_by, recipients, cursor,
created_at, updated_at, done_at)`: one row for each announcement a repository owes the libraries
that hold it, written in the transaction of the release (or the rollback, or the flip to private)
it announces. `recipients` is the libraries to tell as they were then, `cursor` how many of them
have been told; a drain writes a chunk of notices and moves the cursor in one transaction.

A tenant table of the repository: `tenant_isolation` and `FORCE ROW LEVEL SECURITY`. The sweep
that finishes announcements reads and moves rows of every repository, so three more policies open
for SELECT, UPDATE and DELETE (and for nothing else: a row is only ever written in the
transaction of its release) while `app.fanout_sweep` is `on`, which only that process sets
(ADR 0092's pattern, no `SECURITY DEFINER`). The setting is read with `missing_ok`, and so is the
tenant: the sweep runs with no tenant at all.

Revision ID: b9f3d5a7c1e2
Revises: d4e7a1c9b538
Create Date: 2026-10-15 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b9f3d5a7c1e2"
down_revision: str | None = "d4e7a1c9b538"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_SWEEP = "current_setting('app.fanout_sweep', true) = 'on'"


def upgrade() -> None:
    op.create_table(
        "release_fanout",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("recipients", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("cursor", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["release_id", "tenant_id"],
            ["repository_release.id", "repository_release.tenant_id"],
            name="release_fanout_release_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "cursor >= 0 AND cursor <= cardinality(recipients)", name="release_fanout_cursor"
        ),
        sa.CheckConstraint(
            "done_at IS NULL OR cursor = cardinality(recipients)", name="release_fanout_done"
        ),
    )
    op.create_index("ix_release_fanout_tenant_id", "release_fanout", ["tenant_id"])
    op.create_index("ix_release_fanout_created_by", "release_fanout", ["created_by"])
    op.create_index(
        "ix_release_fanout_pending",
        "release_fanout",
        ["created_at", "id"],
        postgresql_where=sa.text("done_at IS NULL"),
    )
    op.execute("ALTER TABLE release_fanout ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE release_fanout FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON release_fanout USING (tenant_id = {_TENANT})")
    op.execute(f"CREATE POLICY fanout_sweep_read ON release_fanout FOR SELECT USING ({_SWEEP})")
    op.execute(
        "CREATE POLICY fanout_sweep_update ON release_fanout FOR UPDATE "
        f"USING ({_SWEEP}) WITH CHECK ({_SWEEP})"
    )
    op.execute(f"CREATE POLICY fanout_sweep_delete ON release_fanout FOR DELETE USING ({_SWEEP})")


def downgrade() -> None:
    op.drop_table("release_fanout")
