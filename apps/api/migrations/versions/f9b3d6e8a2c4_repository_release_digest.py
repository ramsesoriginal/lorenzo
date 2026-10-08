"""the digest of a release and the rows it released (ADR 0208)

repository_released_row holds, for each row the update engine compares (a stat group, a stat
definition, an entity, an attachment), the hash of what it was at the repository's last
publish and the few facts the breaking-change detector needs. It is one set per repository,
replaced at each publish; a tenant table with tenant_isolation and, because the libraries a
repository is granted to read it to mark their updates, repository_read (ADR 0118).
repository_release gains the digest over those hashes, what the release added, changed and
removed, and the rows it was acknowledged as breaking.

Revision ID: f9b3d6e8a2c4
Revises: e8a2c5b7d1f3
Create Date: 2026-10-08 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9b3d6e8a2c4"
down_revision: str | None = "e8a2c5b7d1f3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    op.add_column("repository_release", sa.Column("digest", sa.Text(), nullable=True))
    op.add_column("repository_release", sa.Column("counts", postgresql.JSONB(), nullable=True))
    op.add_column(
        "repository_release",
        sa.Column(
            "breaking_rows",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "repository_release",
        sa.Column(
            "warning_rows",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.create_table(
        "repository_released_row",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        # The row's origin id, the id a library's copy link holds; an attachment's child.
        sa.Column("row_id", sa.UUID(), nullable=False),
        # An attachment's parent, null for every other kind.
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "facts",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN ('entity', 'stat_group', 'stat_definition', 'attachment')",
            name="repository_released_row_kind",
        ),
        sa.CheckConstraint(
            "(kind = 'attachment') = (parent_id IS NOT NULL)",
            name="repository_released_row_parent",
        ),
    )
    op.create_index(
        "ix_repository_released_row_tenant_id", "repository_released_row", ["tenant_id"]
    )
    # One row for each key: the key of an attachment is its pair of ids.
    op.execute(
        "CREATE UNIQUE INDEX uq_repository_released_row_key ON repository_released_row "
        "(tenant_id, kind, row_id, COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'))"
    )
    op.execute("ALTER TABLE repository_released_row ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE repository_released_row FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON repository_released_row USING (tenant_id = {_TENANT})"
    )
    op.execute(
        "CREATE POLICY repository_read ON repository_released_row FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.drop_table("repository_released_row")
    op.drop_column("repository_release", "warning_rows")
    op.drop_column("repository_release", "breaking_rows")
    op.drop_column("repository_release", "counts")
    op.drop_column("repository_release", "digest")
