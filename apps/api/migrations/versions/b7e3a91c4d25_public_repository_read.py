"""the public branch of the gated repository read (ADR 0287)

`repository_read_tenant_id()` returned the requested repository only for a tenant holding a
grant to it. It now returns it as well when the repository's profile says `public`, whoever
asks and with no current tenant: a published, public repository is readable by anyone logged in
(RFC 0038 section 3), still only inside `reading_repository`, still `FOR SELECT`.

The function reads the profile, and the profile's own `repository_read` policy called the
function: a policy that reaches its own table through a function is an infinite recursion for
Postgres. The profile's policy is now written out (published, and public or granted) and does
not call the function; every other table's still does.

The insert policy of `repository_subscription` gains a second case: a library may write its own
grant, `source = 'public'`, to a repository that is public and published. The repository's side
still writes `invited` only, as in revision a1d4c7e9b203.

Revision ID: b7e3a91c4d25
Revises: c4a2f7e91b35
Create Date: 2026-10-14 09:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b7e3a91c4d25"
down_revision: str | None = "c4a2f7e91b35"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_REQUESTED = "NULLIF(current_setting('app.repository_tenant_id', true), '')::uuid"

_SUBSCRIBED_REPOSITORY = "repository_subscription.repository_tenant_id"
_PUBLISHED_REPOSITORY = (
    "SELECT 1 FROM tenant t WHERE t.id = {id} AND t.kind = 'repository' "
    "AND t.published_at IS NOT NULL"
)
_GRANT = (
    "SELECT 1 FROM repository_subscription s "
    f"WHERE s.repository_tenant_id = {{id}} AND s.subscriber_tenant_id = {_CURRENT_TENANT}"
)

# The whole rule in one place, as before: the repository this request asked to read, if it is
# published and either the current tenant holds a grant for it or it is public; otherwise null,
# which no row's tenant_id equals.
_READ_TENANT_FUNCTION = f"""
CREATE OR REPLACE FUNCTION repository_read_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT t.id
    FROM tenant t
    WHERE t.id = {_REQUESTED}
      AND t.kind = 'repository'
      AND t.published_at IS NOT NULL
      AND (
        EXISTS ({_GRANT.format(id="t.id")})
        OR EXISTS (SELECT 1 FROM repository_profile p
                   WHERE p.tenant_id = t.id AND p.visibility = 'public')
      )
$$;
"""

# The original, a grant and a published repository.
_OLD_READ_TENANT_FUNCTION = f"""
CREATE OR REPLACE FUNCTION repository_read_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT s.repository_tenant_id
    FROM repository_subscription s
    JOIN tenant t ON t.id = s.repository_tenant_id
    WHERE s.repository_tenant_id = {_REQUESTED}
      AND s.subscriber_tenant_id = {_CURRENT_TENANT}
      AND t.kind = 'repository'
      AND t.published_at IS NOT NULL
$$;
"""


def upgrade() -> None:
    # The profile's policy first, so that nothing calls the function while it reads the profile.
    op.execute("DROP POLICY repository_read ON repository_profile")
    op.execute(
        "CREATE POLICY repository_read ON repository_profile FOR SELECT USING ("
        f"tenant_id = {_REQUESTED} "
        f"AND EXISTS ({_PUBLISHED_REPOSITORY.format(id='repository_profile.tenant_id')}) "
        "AND (visibility = 'public' "
        f"OR EXISTS ({_GRANT.format(id='repository_profile.tenant_id')})))"
    )
    op.execute(_READ_TENANT_FUNCTION)

    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(
        "CREATE POLICY repository_subscription_grant ON repository_subscription FOR INSERT "
        "WITH CHECK ("
        f"(repository_tenant_id = {_CURRENT_TENANT} AND source = 'invited') "
        f"OR (subscriber_tenant_id = {_CURRENT_TENANT} AND source = 'public' "
        f"AND EXISTS ({_PUBLISHED_REPOSITORY.format(id=_SUBSCRIBED_REPOSITORY)}) "
        "AND EXISTS (SELECT 1 FROM repository_profile p "
        f"WHERE p.tenant_id = {_SUBSCRIBED_REPOSITORY} "
        "AND p.visibility = 'public')))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(
        "CREATE POLICY repository_subscription_grant ON repository_subscription FOR INSERT "
        f"WITH CHECK (repository_tenant_id = {_CURRENT_TENANT} AND source = 'invited')"
    )
    op.execute(_OLD_READ_TENANT_FUNCTION)
    op.execute("DROP POLICY repository_read ON repository_profile")
    op.execute(
        "CREATE POLICY repository_read ON repository_profile FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )
