"""repository_copy_link_attachment: the parents a bridge added to its copies (ADR 0172)

A tenant that copies a repository takes the parents it attached to entities it
holds copies of, as well as its own rows. This table records, per tenant, which
attachments it took from which repository, as a pair of origin ids: without it, a
later removal could not be told from an edge the tenant added itself.

Copy bookkeeping, not repository content: it belongs to the copying tenant
(tenant_isolation) and is not readable through the gated repository read (ADR 0118).
The ids are plain ids, never foreign keys: they are origins, which are other
tenants' rows and may go.

Revision ID: a7c3f95e2b18
Revises: d4e8a1b6c2f7
Create Date: 2026-10-04 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3f95e2b18"
down_revision: str | None = "d4e8a1b6c2f7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLE = "repository_copy_link_attachment"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source_tenant_id", sa.UUID(), nullable=False),
        sa.Column("child_source_id", sa.UUID(), nullable=False),
        sa.Column("parent_source_id", sa.UUID(), nullable=False),
        sa.Column(
            "copied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint(
            "tenant_id", "source_tenant_id", "child_source_id", "parent_source_id"
        ),
    )
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {_TABLE} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
