"""an Owner can deprecate a repository (ADR 0384)

`tenant` gains `deprecated_at` and `deprecated_message`: a repository its Owner retired (RFC 0038
section 7). A deprecated repository leaves the listing, blocks new copies, and stops being open to
visitors; the libraries that hold it (a grant, which a copy of a public repository always writes)
keep reading it and keep their updates. The message is optional.

The columns are on `tenant`, beside `published_at` and `delisted_at`, for the reason revision
d4e7a1c9b538 gave: a policy that has to know whether a repository is open to outside readers reads
the tenant row, which no policy hides.

The rule that decides who may read a repository is written in four places in the database, and
this changes each of them the same way. Deprecating closes the public branch of the rule and
nothing else, so a library with a grant still passes:

- `repository_read_tenant_id()`, the gate every content table's `repository_read` policy calls:
  published, not delisted, and a grant, or public and not deprecated.
- The profile's own `repository_read`, which does not call the function (revision b7e3a91c4d25).
- `discover_read` on the profile, which lists public repositories: not deprecated.
- The insert policy of `repository_subscription`, where a library writes its own `public` grant:
  not deprecated.

Revision ID: e1b6d4a9c370
Revises: c03810000001
Create Date: 2026-11-03 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1b6d4a9c370"
down_revision: str | None = "c03810000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_REQUESTED = "NULLIF(current_setting('app.repository_tenant_id', true), '')::uuid"
_SUBSCRIBED_REPOSITORY = "repository_subscription.repository_tenant_id"
_GRANT = (
    "SELECT 1 FROM repository_subscription s "
    f"WHERE s.repository_tenant_id = {{id}} AND s.subscriber_tenant_id = {_CURRENT_TENANT}"
)
_OPEN = "t.published_at IS NOT NULL AND t.delisted_at IS NULL"


def _public_branch(*, deprecating: bool) -> str:
    """What lets a reader in without a grant: the profile says `public` and, from this revision
    on, the Owner has not retired it. `t` is the tenant row."""
    return "t.deprecated_at IS NULL AND " if deprecating else ""


def _published_repository(*, deprecating: bool, public: bool = False) -> str:
    """The tenant row of a published, listed-or-not repository that is not delisted; `public`
    adds the condition of the public branch (not deprecated)."""
    return f"SELECT 1 FROM tenant t WHERE t.id = {{id}} AND t.kind = 'repository' AND {_OPEN}" + (
        " AND t.deprecated_at IS NULL" if public and deprecating else ""
    )


def _read_tenant_function(*, deprecating: bool) -> str:
    return f"""
CREATE OR REPLACE FUNCTION repository_read_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT t.id
    FROM tenant t
    WHERE t.id = {_REQUESTED}
      AND t.kind = 'repository'
      AND {_OPEN}
      AND (
        EXISTS ({_GRANT.format(id="t.id")})
        OR ({_public_branch(deprecating=deprecating)}EXISTS (
                   SELECT 1 FROM repository_profile p
                   WHERE p.tenant_id = t.id AND p.visibility = 'public'))
      )
$$;
"""


def _profile_read_policy(*, deprecating: bool) -> str:
    # `t` of the subquery is the tenant row of the profile's repository: a visitor reads it
    # while it is public and not retired, a library with a grant whatever its state.
    return (
        "CREATE POLICY repository_read ON repository_profile FOR SELECT USING ("
        f"tenant_id = {_REQUESTED} "
        "AND EXISTS ("
        + _published_repository(deprecating=deprecating).format(id="repository_profile.tenant_id")
        + ") "
        "AND ((visibility = 'public'"
        + (
            " AND NOT EXISTS (SELECT 1 FROM tenant d WHERE d.id = repository_profile.tenant_id "
            "AND d.deprecated_at IS NOT NULL)"
            if deprecating
            else ""
        )
        + ") "
        f"OR EXISTS ({_GRANT.format(id='repository_profile.tenant_id')})))"
    )


def _insert_policy(*, deprecating: bool) -> str:
    return (
        "CREATE POLICY repository_subscription_grant ON repository_subscription FOR INSERT "
        "WITH CHECK ("
        f"(repository_tenant_id = {_CURRENT_TENANT} AND source = 'invited') "
        f"OR (subscriber_tenant_id = {_CURRENT_TENANT} AND source = 'public' "
        "AND EXISTS ("
        + _published_repository(deprecating=deprecating, public=True).format(
            id=_SUBSCRIBED_REPOSITORY
        )
        + ") "
        "AND EXISTS (SELECT 1 FROM repository_profile p "
        f"WHERE p.tenant_id = {_SUBSCRIBED_REPOSITORY} "
        "AND p.visibility = 'public')))"
    )


def _discover_policy(*, deprecating: bool) -> str:
    return (
        "CREATE POLICY discover_read ON repository_profile FOR SELECT USING ("
        "visibility = 'public' AND release_label IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM tenant t WHERE t.id = repository_profile.tenant_id "
        f"AND t.kind = 'repository' AND {_OPEN}"
        + (" AND t.deprecated_at IS NULL" if deprecating else "")
        + "))"
    )


def upgrade() -> None:
    op.add_column("tenant", sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenant", sa.Column("deprecated_message", sa.Text(), nullable=True))
    # Deprecated or not as a whole: a repository with a time and, if the Owner wrote one, a
    # message of 1 to 500 characters; or nothing.
    op.create_check_constraint(
        "tenant_deprecated",
        "tenant",
        "(deprecated_at IS NULL AND deprecated_message IS NULL) "
        "OR (kind = 'repository' AND deprecated_at IS NOT NULL "
        "AND (deprecated_message IS NULL OR char_length(deprecated_message) BETWEEN 1 AND 500))",
    )

    op.execute(_read_tenant_function(deprecating=True))
    op.execute("DROP POLICY repository_read ON repository_profile")
    op.execute(_profile_read_policy(deprecating=True))
    op.execute("DROP POLICY discover_read ON repository_profile")
    op.execute(_discover_policy(deprecating=True))
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(_insert_policy(deprecating=True))


def downgrade() -> None:
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(_insert_policy(deprecating=False))
    op.execute("DROP POLICY discover_read ON repository_profile")
    op.execute(_discover_policy(deprecating=False))
    op.execute("DROP POLICY repository_read ON repository_profile")
    op.execute(_profile_read_policy(deprecating=False))
    op.execute(_read_tenant_function(deprecating=False))

    op.drop_constraint("tenant_deprecated", "tenant")
    op.drop_column("tenant", "deprecated_message")
    op.drop_column("tenant", "deprecated_at")
