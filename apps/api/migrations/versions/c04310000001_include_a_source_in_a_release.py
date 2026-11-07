"""A repository can include a repository it is built on in its release (ADR 0431, RFC 0051 H1)

`repository_copy.inclusion` is how a repository carries one it copied when a release of it is
made: `show` (what has always happened) or `include`, which makes the source's rows the
repository's own in the release document. The check allows only these two; later slices of the
RFC widen it.

`repository_profile` gains two columns:

- `may_be_included`, the source's terms: whether a repository built on it may include it. Null
  means "the default for the repository's visibility", which the application reads (a private
  repository: no; a public one: yes), so a default is stored as nothing and follows the
  repository when it changes visibility.
- `release_sources`, how the repository's current public release carries each repository it is
  built on: a list of `{id, name, inclusion, licence_label, licence_url}`, null until it makes a
  public release. The storefront reads what a release includes, and its licence, from it, so a
  visitor never has to read a source that may be private; and changing a choice after a release
  was made is a breaking change by comparison with it.

No policy and no gate function changes: the three places that say who may read a repository
(ADR 0287) are about who reads, and nothing here opens a new way in. `repository_copy` already
has its tenant isolation and the Owner's read of who copied it (ADR 0204), which now shows the
choice too; the two profile columns are in a row the existing policies govern.

Revision ID: c04310000001
Revises: c04060000001
Create Date: 2026-11-07 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c04310000001"
down_revision: str | None = "c04060000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repository_copy",
        sa.Column("inclusion", sa.Text(), server_default=sa.text("'show'"), nullable=False),
    )
    op.create_check_constraint(
        "repository_copy_inclusion", "repository_copy", "inclusion IN ('show', 'include')"
    )
    op.add_column("repository_profile", sa.Column("may_be_included", sa.Boolean(), nullable=True))
    op.add_column(
        "repository_profile",
        sa.Column("release_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("repository_profile", "release_sources")
    op.drop_column("repository_profile", "may_be_included")
    op.drop_constraint("repository_copy_inclusion", "repository_copy", type_="check")
    op.drop_column("repository_copy", "inclusion")
