"""what Discover lists of a repository, and who may read it (ADR 0292)

`repository_profile` keeps the facts a listing shows of the repository's current release: its
label and date, and the size of its content (entries and stat definitions), written whenever a
release is published or made current, so that a listing is one query over the profiles and never
opens a document. A listing reads the profile of every public repository, so the profile gets a
second `FOR SELECT` policy, `discover_read`: a public repository that is published and has a
release, whoever asks and whatever they have asked to read (RFC 0038 section 2). It reaches no
other table.

Revision ID: f3a9c6d2b841
Revises: e5b8c2a7d913
Create Date: 2026-10-14 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a9c6d2b841"
down_revision: str | None = "e5b8c2a7d913"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("repository_profile", sa.Column("release_label", sa.Text(), nullable=True))
    op.add_column(
        "repository_profile", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("repository_profile", sa.Column("entry_count", sa.Integer(), nullable=True))
    op.add_column(
        "repository_profile", sa.Column("stat_definition_count", sa.Integer(), nullable=True)
    )
    # The repositories that have a release have its facts too: the label and the date from the
    # ledger; the size is written by the next publish, since only a document or a load knows it.
    op.execute(
        "UPDATE repository_profile p SET release_label = r.label, released_at = r.created_at "
        "FROM tenant t JOIN repository_release r ON r.id = t.current_release_id "
        "AND r.tenant_id = t.id WHERE t.id = p.tenant_id"
    )
    op.execute(
        "CREATE POLICY discover_read ON repository_profile FOR SELECT USING ("
        "visibility = 'public' AND release_label IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM tenant t WHERE t.id = repository_profile.tenant_id "
        "AND t.kind = 'repository' AND t.published_at IS NOT NULL))"
    )
    op.create_index(
        "ix_repository_profile_listed",
        "repository_profile",
        ["released_at"],
        postgresql_where=sa.text("visibility = 'public'"),
    )


def downgrade() -> None:
    op.drop_index("ix_repository_profile_listed", table_name="repository_profile")
    op.execute("DROP POLICY discover_read ON repository_profile")
    op.drop_column("repository_profile", "stat_definition_count")
    op.drop_column("repository_profile", "entry_count")
    op.drop_column("repository_profile", "released_at")
    op.drop_column("repository_profile", "release_label")
