"""A public repository can be left off Discover (ADR 0432, RFC 0051 H2)

`repository_profile.listed` is whether Discover lists a public repository: true by default, and an
Owner of a public repository may set it false. An unlisted repository is public in every other
way: its storefront and its `/repositories/{id}` reads answer for anyone signed in who has the
address, and a library copies it by address. Only the listing, its facets and its search leave it
out.

A check ties the flag to the visibility: `listed OR visibility = 'public'`. Not listed is a
fact about a public repository only, so the flips put it back to listed when a repository stops
being public, and a repository that becomes public starts listed. The check makes a flip that
forgets it fail loudly instead of leaving a repository that is quietly unlisted the next time it
is made public.

The rule that says what Discover lists is written in two places that must say the same thing, and
this changes both: `discover.listed()` in the application, and the `discover_read` policy on the
profile, the second `FOR SELECT` policy that ADR 0292 gave it (and ADR 0303 and ADR 0384
narrowed). The policy gains `listed`, so that a listing query which forgot the condition still
could not read an unlisted repository's profile through it. `repository_read`, the profile's other
policy, the gate function and the insert policy of `repository_subscription` are about who may
read or copy a repository by its address, and an unlisted one is read and copied like any
public one: none of them changes.

Revision ID: c04320000001
Revises: c04310000001
Create Date: 2026-11-07 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c04320000001"
down_revision: str | None = "c04310000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _discover_policy(*, unlisted: bool) -> str:
    """`discover_read` as ADR 0384 left it, and from this revision on also `listed`."""
    return (
        "CREATE POLICY discover_read ON repository_profile FOR SELECT USING ("
        "visibility = 'public' AND release_label IS NOT NULL"
        + (" AND listed" if unlisted else "")
        + " AND EXISTS (SELECT 1 FROM tenant t WHERE t.id = repository_profile.tenant_id "
        "AND t.kind = 'repository' AND t.published_at IS NOT NULL AND t.delisted_at IS NULL "
        "AND t.deprecated_at IS NULL))"
    )


def upgrade() -> None:
    op.add_column(
        "repository_profile",
        sa.Column("listed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_check_constraint(
        "repository_profile_listed", "repository_profile", "listed OR visibility = 'public'"
    )
    op.execute("DROP POLICY discover_read ON repository_profile")
    op.execute(_discover_policy(unlisted=True))


def downgrade() -> None:
    op.execute("DROP POLICY discover_read ON repository_profile")
    op.execute(_discover_policy(unlisted=False))
    op.drop_constraint("repository_profile_listed", "repository_profile", type_="check")
    op.drop_column("repository_profile", "listed")
