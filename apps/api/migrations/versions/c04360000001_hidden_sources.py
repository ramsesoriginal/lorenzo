"""A repository built on another can hide its entries from the libraries that copy it (ADR 0437,
RFC 0051 H4)

`repository_copy.inclusion` gains `hide`: a repository carries a source separate, and the entries
of the source are hidden in the libraries that hold them through it.

- `repository_copy.carries` is the library's own record of what each repository it holds brings
  separate: `{<source id>: "show" | "hide"}`, taken from the release it last took, plus the
  repository's own id as `show` where the library copied it for itself. The flag below is derived
  from it, so the derivation reads nothing of another repository. Existing records carry
  themselves as `show`: what a library holds today is never hidden by a choice made later.
- `repository_copy_link_entity.hidden` is the flag on the copy link of each row (RFC 0051): true
  while every repository the library holds that brings the row's repository hides it. A partial
  index serves the gate's `NOT EXISTS`.
- `tenant.hides_entries` says whether any link of the tenant is hidden, so that every read of an
  entry asks the gate its one extra question only where there is something to hide, and a tenant
  that hides nothing pays nothing.
- `repository_profile.may_be_hidden` is A's third term, next to `may_be_included` and
  `may_be_shown`: nullable, null the default for the visibility.

No policy and no table: the three columns sit in rows the existing policies govern.

Revision ID: c04360000001
Revises: c04330000001
Create Date: 2026-11-07 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c04360000001"
down_revision: str | None = "c04330000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("repository_copy_inclusion", "repository_copy", type_="check")
    op.create_check_constraint(
        "repository_copy_inclusion",
        "repository_copy",
        "inclusion IN ('show', 'include', 'hide')",
    )
    op.add_column(
        "repository_copy",
        sa.Column(
            "carries",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE repository_copy "
        "SET carries = jsonb_build_object(repository_tenant_id::text, 'show')"
    )
    op.add_column(
        "repository_copy_link_entity",
        sa.Column("hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "ix_repository_copy_link_entity_hidden",
        "repository_copy_link_entity",
        ["entity_id"],
        postgresql_where=sa.text("hidden"),
    )
    op.add_column(
        "tenant",
        sa.Column("hides_entries", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("repository_profile", sa.Column("may_be_hidden", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("repository_profile", "may_be_hidden")
    op.drop_column("tenant", "hides_entries")
    op.drop_index("ix_repository_copy_link_entity_hidden", "repository_copy_link_entity")
    op.drop_column("repository_copy_link_entity", "hidden")
    op.drop_column("repository_copy", "carries")
    op.execute("UPDATE repository_copy SET inclusion = 'show' WHERE inclusion = 'hide'")
    op.drop_constraint("repository_copy_inclusion", "repository_copy", type_="check")
    op.create_check_constraint(
        "repository_copy_inclusion", "repository_copy", "inclusion IN ('show', 'include')"
    )
