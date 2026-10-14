"""the release a library reads, on the repository (ADR 0288)

`tenant.current_release_id`: the release of a repository that other tenants read (RFC 0037 section
5). A publish makes its release current; "make release current" points it at an earlier one whose
document is still kept. A same-tenant key, as `weapon_stat_group_id` is (ADR 0281): composite with
the tenant's own id, so it can name only a release of the repository itself, and cleared, not the
tenant, if the release is ever deleted. The repositories that exist have it set to their newest
release, which is what a library read until now.

Revision ID: e5b8c2a7d913
Revises: b7e3a91c4d25
Create Date: 2026-10-14 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b8c2a7d913"
down_revision: str | None = "b7e3a91c4d25"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("current_release_id", sa.Uuid(), nullable=True))
    op.execute(
        "ALTER TABLE tenant ADD CONSTRAINT tenant_current_release_id_fkey "
        "FOREIGN KEY (current_release_id, id) REFERENCES repository_release (id, tenant_id) "
        "ON DELETE SET NULL (current_release_id)"
    )
    op.execute(
        "UPDATE tenant t SET current_release_id = ("
        "SELECT r.id FROM repository_release r WHERE r.tenant_id = t.id "
        "ORDER BY r.number DESC LIMIT 1) WHERE t.kind = 'repository'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tenant DROP CONSTRAINT tenant_current_release_id_fkey")
    op.drop_column("tenant", "current_release_id")
