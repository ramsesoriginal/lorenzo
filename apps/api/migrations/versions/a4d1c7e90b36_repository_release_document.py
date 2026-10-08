"""the release document and its files (ADR 0214)

repository_release_document holds a release's content as it was, gzipped JSON in the format
named by its `format` column, one document for each release, with a same-tenant key to the
release. repository_release_blob holds the bytes of the pictures and documents those refer to,
by SHA-256, once for each repository. Both are immutable (a trigger refuses an update, for
every role; a delete is allowed, for retention and for a tenant's deletion) and are tenant
tables of the repository with tenant_isolation and, because the libraries it is granted to
read them, repository_read (ADR 0118).

Revision ID: a4d1c7e90b36
Revises: f9b3d6e8a2c4
Create Date: 2026-10-08 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4d1c7e90b36"
down_revision: str | None = "f9b3d6e8a2c4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"
_TABLES = ("repository_release_document", "repository_release_blob")

# Separate op.execute() calls for each statement - asyncpg prepares every statement it sends,
# and one prepared statement can't hold two commands.
_IMMUTABLE_FUNCTION = """
CREATE FUNCTION repository_release_row_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% rows can''t change: a release document is kept as it was written',
        TG_TABLE_NAME
        USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "repository_release_document",
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("format", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "blobs",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["release_id", "tenant_id"],
            ["repository_release.id", "repository_release.tenant_id"],
            name="repository_release_document_release_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("release_id"),
        sa.CheckConstraint("format > 0", name="repository_release_document_format"),
    )
    op.create_index(
        "ix_repository_release_document_tenant_id", "repository_release_document", ["tenant_id"]
    )
    op.create_table(
        "repository_release_blob",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id", "sha256"),
    )

    op.execute(_IMMUTABLE_FUNCTION)
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = {_TENANT})")
        op.execute(
            f"CREATE POLICY repository_read ON {table} FOR SELECT "
            "USING (tenant_id = (SELECT repository_read_tenant_id()))"
        )
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION repository_release_row_immutable()"
        )


def downgrade() -> None:
    op.drop_table("repository_release_blob")
    op.drop_table("repository_release_document")
    op.execute("DROP FUNCTION repository_release_row_immutable()")
