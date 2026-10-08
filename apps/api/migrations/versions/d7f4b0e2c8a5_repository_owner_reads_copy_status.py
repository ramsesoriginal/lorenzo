"""the repository a copy came from may read the copy record (ADR 0204)

One more SELECT policy on repository_copy: a row is visible to the tenant
it was copied from, so a repository's members can say which tenants copied
it and when they last updated. Nothing is written, and no other table is
touched; writes stay under tenant_isolation.

Revision ID: d7f4b0e2c8a5
Revises: c6e3a9d1b7f4
Create Date: 2026-10-08 09:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d7f4b0e2c8a5"
down_revision: str | None = "c6e3a9d1b7f4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE POLICY repository_owner_read ON repository_copy FOR SELECT "
        "USING (repository_tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY repository_owner_read ON repository_copy")
