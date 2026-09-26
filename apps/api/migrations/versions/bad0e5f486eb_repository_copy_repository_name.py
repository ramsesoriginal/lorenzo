"""repository_copy.repository_name: a copy remembers what it was a copy of (ADR 0119)

GET .../repositories lists repositories a tenant has copied as well as
those it's granted, so a copy stays visible after its grant is gone. A
repository can also be deleted since; its name at copy time, refreshed
on every sync, is what the listing shows then.

Revision ID: bad0e5f486eb
Revises: d6c365a78ba3
Create Date: 2026-09-25 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bad0e5f486eb"
down_revision: str | None = "d6c365a78ba3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repository_copy",
        sa.Column("repository_name", sa.Text(), server_default="", nullable=False),
    )
    # Copies made before this revision: their repository's current name, if
    # it still exists.
    op.execute(
        "UPDATE repository_copy c SET repository_name = t.name "
        "FROM tenant t WHERE t.id = c.repository_tenant_id"
    )


def downgrade() -> None:
    op.drop_column("repository_copy", "repository_name")
