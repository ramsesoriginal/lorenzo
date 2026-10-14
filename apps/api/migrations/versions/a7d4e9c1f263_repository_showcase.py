"""the entries an Owner features in a repository's preview (ADR 0293)

`repository_showcase(tenant_id, entity_id, position)`: the entries an Owner chose to show a
visitor before they copy (RFC 0038 section 5), in the order they chose, a key to the repository's
own entry. A tenant table of the repository: `tenant_isolation` and `FORCE ROW LEVEL SECURITY`,
and `repository_read`, because the libraries and visitors that look at the preview read it inside
the gated read. A copy never carries it.

Revision ID: a7d4e9c1f263
Revises: f3a9c6d2b841
Create Date: 2026-10-14 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7d4e9c1f263"
down_revision: str | None = "f3a9c6d2b841"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    op.create_table(
        "repository_showcase",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["entity_id", "tenant_id"],
            ["entity.id", "entity.tenant_id"],
            name="repository_showcase_entity_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.CheckConstraint("position >= 0", name="repository_showcase_position"),
    )
    op.create_index("ix_repository_showcase_tenant_id", "repository_showcase", ["tenant_id"])
    op.execute("ALTER TABLE repository_showcase ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE repository_showcase FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON repository_showcase USING (tenant_id = {_TENANT})"
    )
    op.execute(
        "CREATE POLICY repository_read ON repository_showcase FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.drop_table("repository_showcase")
