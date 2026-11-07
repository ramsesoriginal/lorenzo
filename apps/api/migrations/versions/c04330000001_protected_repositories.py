"""A repository can be protected (ADR 0433, RFC 0051 H3)

`repository_profile.visibility` gains `protected`: a repository that has a profile and a release
document like a public one, is on no listing, and is read by a library only as a step of the copy
of a public repository that is built on it. The rest of this revision is the gate that says so.

**The one function.** `repository_reached_through_another(a)` is the rule: the request has gone
through a repository `v` (the transaction-local `app.repository_via`, set by `reading_repository`
and by nothing else) that is a published, undelisted repository whose current public release lists
`a` (`tenant.released_over` holds `a` and `tenant.released_public` is true), for a tenant that is a
tenant (a request in none is `NO_TENANT` and has no row), and that is not retired, unless the
tenant holds a grant to it already; and `a` itself is a published, undelisted repository, not
retired unless the tenant holds a grant to it already. It reads `tenant` (no policy) and the
`repository_subscription` rows of the tenant and nothing else (the copy records are read through
the gate itself, which would recurse), which is what lets the profile's own policy call it: the
recursion ADR 0287 found is a policy that reaches its own table.

**Why the facts about `v` are on `tenant`.** The rule has to know that `v` is public and that its
current release lists `a`. Both are in `v`'s profile, which no policy lets another tenant's request
read with `a` as the requested repository, and a policy on the profile that reads the profile is
the recursion. So the two facts that matter are kept on `tenant`, beside `published_at`,
`delisted_at` and `deprecated_at`, for the reason revision d4e7a1c9b538 gave: a policy that has to
know something of another repository reads a row nothing hides. `released_over` is the
repositories the current release of a public or protected repository was built on and did not
include (empty while it is private), `released_public` whether it is public. The application
writes both whenever the profile's `release_sources` or `visibility` change
(`repository_reach.sync_reach`), and a test holds them to the profile.

**What changes with it.**

- The gate `repository_read_tenant_id()` and the profile's own `repository_read` gain the case: a
  protected repository is read when the function says so. Both also stop counting a grant whose
  `source` is `protected` as one: that row is how the library lists what it holds and never lets it
  read anything alone.
- The insert policy of `repository_subscription` gains the library writing its own `protected` row
  to a protected repository, inside the read the function allows.
- A narrow update policy lets a repository's side turn its `public` rows into `protected` ones when
  it becomes protected, and back when it becomes public again: the only UPDATE the table has ever
  had, and it can write nothing else.
- `repository_profile.may_be_shown` is A's second term, next to `may_be_included`: nullable, null is
  the default for the visibility.

Revision ID: c04330000001
Revises: c04320000001
Create Date: 2026-11-07 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c04330000001"
down_revision: str | None = "c04320000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_REQUESTED = "NULLIF(current_setting('app.repository_tenant_id', true), '')::uuid"
_VIA = "NULLIF(current_setting('app.repository_via', true), '')::uuid"
_SUBSCRIBED_REPOSITORY = "repository_subscription.repository_tenant_id"
_OPEN = "t.published_at IS NOT NULL AND t.delisted_at IS NULL"


def _grant(*, protected: bool) -> str:
    """A grant of the current tenant to `{id}`; a `protected` row is not one, from this revision."""
    return (
        "SELECT 1 FROM repository_subscription s "
        f"WHERE s.repository_tenant_id = {{id}} AND s.subscriber_tenant_id = {_CURRENT_TENANT}"
        + (" AND s.source <> 'protected'" if protected else "")
    )


_REACHED_FUNCTION = f"""
CREATE OR REPLACE FUNCTION repository_reached_through_another(a uuid) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT EXISTS (
        SELECT 1
        FROM tenant me, tenant v, tenant s
        WHERE me.id = {_CURRENT_TENANT}
          AND v.id = {_VIA}
          AND v.kind = 'repository'
          AND v.published_at IS NOT NULL
          AND v.delisted_at IS NULL
          AND v.released_public
          AND a = ANY (v.released_over)
          AND s.id = a
          AND s.kind = 'repository'
          AND (v.deprecated_at IS NULL OR EXISTS (
                 SELECT 1 FROM repository_subscription c
                 WHERE c.subscriber_tenant_id = me.id AND c.repository_tenant_id = v.id))
          AND (s.deprecated_at IS NULL OR EXISTS (
                 SELECT 1 FROM repository_subscription c
                 WHERE c.subscriber_tenant_id = me.id AND c.repository_tenant_id = s.id))
    )
$$;
"""


def _read_tenant_function(*, protected: bool) -> str:
    """The gate every content table's `repository_read` calls, as ADR 0384 left it and, from this
    revision on, with the protected case."""
    reached = (
        """
        OR (EXISTS (SELECT 1 FROM repository_profile p
                    WHERE p.tenant_id = t.id AND p.visibility = 'protected')
            AND repository_reached_through_another(t.id))"""
        if protected
        else ""
    )
    return f"""
CREATE OR REPLACE FUNCTION repository_read_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT t.id
    FROM tenant t
    WHERE t.id = {_REQUESTED}
      AND t.kind = 'repository'
      AND {_OPEN}
      AND (
        EXISTS ({_grant(protected=protected).format(id="t.id")})
        OR (t.deprecated_at IS NULL AND EXISTS (
                   SELECT 1 FROM repository_profile p
                   WHERE p.tenant_id = t.id AND p.visibility = 'public')){reached}
      )
$$;
"""


def _profile_read_policy(*, protected: bool) -> str:
    """The profile's own `repository_read`, which does not call the gate (revision b7e3a91c4d25)."""
    reached = (
        " OR (visibility = 'protected' "
        "AND repository_reached_through_another(repository_profile.tenant_id))"
        if protected
        else ""
    )
    return (
        "CREATE POLICY repository_read ON repository_profile FOR SELECT USING ("
        f"tenant_id = {_REQUESTED} "
        "AND EXISTS ("
        "SELECT 1 FROM tenant t WHERE t.id = repository_profile.tenant_id "
        f"AND t.kind = 'repository' AND {_OPEN}) "
        "AND ((visibility = 'public' AND NOT EXISTS (SELECT 1 FROM tenant d "
        "WHERE d.id = repository_profile.tenant_id AND d.deprecated_at IS NOT NULL))"
        f"{reached} "
        f"OR EXISTS ({_grant(protected=protected).format(id='repository_profile.tenant_id')})))"
    )


def _insert_policy(*, protected: bool) -> str:
    reached = (
        f" OR (subscriber_tenant_id = {_CURRENT_TENANT} AND source = 'protected' "
        "AND EXISTS (SELECT 1 FROM tenant t "
        f"WHERE t.id = {_SUBSCRIBED_REPOSITORY} AND t.kind = 'repository' AND {_OPEN}) "
        "AND EXISTS (SELECT 1 FROM repository_profile p "
        f"WHERE p.tenant_id = {_SUBSCRIBED_REPOSITORY} AND p.visibility = 'protected') "
        f"AND repository_reached_through_another({_SUBSCRIBED_REPOSITORY}))"
        if protected
        else ""
    )
    return (
        "CREATE POLICY repository_subscription_grant ON repository_subscription FOR INSERT "
        "WITH CHECK ("
        f"(repository_tenant_id = {_CURRENT_TENANT} AND source = 'invited') "
        f"OR (subscriber_tenant_id = {_CURRENT_TENANT} AND source = 'public' "
        "AND EXISTS (SELECT 1 FROM tenant t "
        f"WHERE t.id = {_SUBSCRIBED_REPOSITORY} AND t.kind = 'repository' AND {_OPEN} "
        "AND t.deprecated_at IS NULL) "
        "AND EXISTS (SELECT 1 FROM repository_profile p "
        f"WHERE p.tenant_id = {_SUBSCRIBED_REPOSITORY} AND p.visibility = 'public'))"
        f"{reached})"
    )


_UPDATE_POLICY = (
    "CREATE POLICY repository_subscription_source ON repository_subscription FOR UPDATE "
    f"USING (repository_tenant_id = {_CURRENT_TENANT} AND source IN ('public', 'protected')) "
    f"WITH CHECK (repository_tenant_id = {_CURRENT_TENANT} AND source IN ('public', 'protected'))"
)


def upgrade() -> None:
    op.drop_constraint("repository_profile_visibility", "repository_profile", type_="check")
    op.create_check_constraint(
        "repository_profile_visibility",
        "repository_profile",
        "visibility IN ('private', 'protected', 'public')",
    )
    op.add_column("repository_profile", sa.Column("may_be_shown", sa.Boolean(), nullable=True))

    op.drop_constraint("repository_subscription_source", "repository_subscription", type_="check")
    op.create_check_constraint(
        "repository_subscription_source",
        "repository_subscription",
        "source IN ('invited', 'public', 'protected')",
    )

    op.add_column(
        "tenant",
        sa.Column(
            "released_over",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "tenant",
        sa.Column("released_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        "tenant_released",
        "tenant",
        "kind = 'repository' OR (cardinality(released_over) = 0 AND NOT released_public)",
    )
    # What the public repositories that exist now release over (none in a deployment that has not
    # turned public repositories on): from the record of the current release where it has one, from
    # the copy records where it was made before the record existed. A role that RLS applies to
    # reads no profile here and changes nothing.
    op.execute(
        """
        UPDATE tenant t SET
            released_public = true,
            released_over = CASE
                WHEN p.release_sources IS NULL THEN ARRAY(
                    SELECT c.repository_tenant_id FROM repository_copy c WHERE c.tenant_id = t.id)
                ELSE ARRAY(
                    SELECT (s ->> 'id')::uuid FROM jsonb_array_elements(p.release_sources) s
                    WHERE s ->> 'inclusion' <> 'include')
            END
        FROM repository_profile p
        WHERE p.tenant_id = t.id AND p.visibility = 'public'
        """
    )

    op.execute(_REACHED_FUNCTION)
    op.execute(_read_tenant_function(protected=True))
    op.execute("DROP POLICY repository_read ON repository_profile")
    op.execute(_profile_read_policy(protected=True))
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(_insert_policy(protected=True))
    op.execute(_UPDATE_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY repository_subscription_source ON repository_subscription")
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(_insert_policy(protected=False))
    op.execute("DROP POLICY repository_read ON repository_profile")
    op.execute(_profile_read_policy(protected=False))
    op.execute(_read_tenant_function(protected=False))
    op.execute("DROP FUNCTION repository_reached_through_another(uuid)")

    op.execute("DELETE FROM repository_subscription WHERE source = 'protected'")
    op.execute(
        "UPDATE repository_profile SET visibility = 'private' WHERE visibility = 'protected'"
    )
    op.drop_constraint("tenant_released", "tenant", type_="check")
    op.drop_column("tenant", "released_public")
    op.drop_column("tenant", "released_over")
    op.drop_constraint("repository_subscription_source", "repository_subscription", type_="check")
    op.create_check_constraint(
        "repository_subscription_source",
        "repository_subscription",
        "source IN ('invited', 'public')",
    )
    op.drop_column("repository_profile", "may_be_shown")
    op.drop_constraint("repository_profile_visibility", "repository_profile", type_="check")
    op.create_check_constraint(
        "repository_profile_visibility", "repository_profile", "visibility IN ('private', 'public')"
    )
