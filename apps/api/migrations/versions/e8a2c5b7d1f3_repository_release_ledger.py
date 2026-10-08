"""repository_release, the ledger of what a repository published (ADR 0207)

Publishing a repository makes a release: a number the server assigns, a
free-text label (unique within the repository whatever its case), optional
notes and the author's breaking flag. A tenant table of the repository, so
it carries tenant_isolation and, because the libraries a repository is
granted to read it through the gated read (ADR 0118), repository_read.
Nothing points at it with a foreign key: a copy records the release it last
took as a plain id (repository_copy.synced_release_id), since the copy is
another tenant's row and the repository may go.

Revision ID: e8a2c5b7d1f3
Revises: d7f4b0e2c8a5
Create Date: 2026-10-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8a2c5b7d1f3"
down_revision: str | None = "d7f4b0e2c8a5"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    op.create_table(
        "repository_release",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("breaking", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        # What a later table's same-tenant key points at (ADR 0117).
        sa.UniqueConstraint("id", "tenant_id", name="uq_repository_release_id_tenant_id"),
        sa.UniqueConstraint("tenant_id", "number", name="uq_repository_release_number"),
        sa.CheckConstraint("number > 0", name="repository_release_number"),
        sa.CheckConstraint("char_length(label) BETWEEN 1 AND 80", name="repository_release_label"),
        sa.CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 4000", name="repository_release_notes"
        ),
    )
    op.create_index("ix_repository_release_tenant_id", "repository_release", ["tenant_id"])
    op.create_index("ix_repository_release_created_by", "repository_release", ["created_by"])
    # Unique within the repository, and not by case: "Spring" and "SPRING" are one label.
    op.execute(
        "CREATE UNIQUE INDEX uq_repository_release_label ON repository_release "
        "(tenant_id, lower(label))"
    )
    op.execute("ALTER TABLE repository_release ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE repository_release FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON repository_release USING (tenant_id = {_TENANT})"
    )
    op.execute(
        "CREATE POLICY repository_read ON repository_release FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )

    # The release a copy last took: a plain id, like repository_tenant_id.
    op.add_column("repository_copy", sa.Column("synced_release_id", sa.UUID(), nullable=True))


def downgrade() -> None:
    op.drop_column("repository_copy", "synced_release_id")
    op.drop_table("repository_release")
