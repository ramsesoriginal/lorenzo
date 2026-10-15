"""an operator can delist a repository (ADR 0303)

`tenant` gains `delisted_at`, `delisted_by` and `delist_reason`: a repository the platform's
operators have taken off Discover (RFC 0038 section 6). A delisted repository leaves the
listing, closes to everyone who reads it from outside (a library that was granted it, a
visitor), blocks new copies, and reads as unpublished to all of them; its own members read and
edit it as ever, through their own tenant.

The columns are on `tenant`, beside `published_at`, which they behave like: a policy that has to
know whether a repository is open to outside readers reads the tenant row, which no policy hides.
On the profile they would be invisible to exactly the readers the gate is deciding about (a row
a policy hides reads as "not delisted"), and the operators' list of delisted repositories would
need an opening of its own in the wall of ADR 0002.

The rule that decides who may read a repository is written in four places in the database, and
this changes each of them the same way, by one more condition next to "published":

- `repository_read_tenant_id()`, the gate every content table's `repository_read` policy calls.
- The profile's own `repository_read`, which does not call the function (revision b7e3a91c4d25).
- `discover_read` on the profile, which lists public repositories.
- The insert policy of `repository_subscription`, where a library writes its own `public` grant.

Revision ID: d4e7a1c9b538
Revises: a8c7d6e5f296
Create Date: 2026-10-15 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e7a1c9b538"
down_revision: str | None = "a8c7d6e5f296"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_REQUESTED = "NULLIF(current_setting('app.repository_tenant_id', true), '')::uuid"
_SUBSCRIBED_REPOSITORY = "repository_subscription.repository_tenant_id"
_GRANT = (
    "SELECT 1 FROM repository_subscription s "
    f"WHERE s.repository_tenant_id = {{id}} AND s.subscriber_tenant_id = {_CURRENT_TENANT}"
)


def _open(*, delisting: bool) -> str:
    """The condition a repository's tenant row must meet to be read from outside: published, and
    from this revision on not delisted."""
    return "t.published_at IS NOT NULL" + (" AND t.delisted_at IS NULL" if delisting else "")


def _published_repository(*, delisting: bool) -> str:
    return (
        "SELECT 1 FROM tenant t WHERE t.id = {id} AND t.kind = 'repository' "
        f"AND {_open(delisting=delisting)}"
    )


def _read_tenant_function(*, delisting: bool) -> str:
    return f"""
CREATE OR REPLACE FUNCTION repository_read_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT t.id
    FROM tenant t
    WHERE t.id = {_REQUESTED}
      AND t.kind = 'repository'
      AND {_open(delisting=delisting)}
      AND (
        EXISTS ({_GRANT.format(id="t.id")})
        OR EXISTS (SELECT 1 FROM repository_profile p
                   WHERE p.tenant_id = t.id AND p.visibility = 'public')
      )
$$;
"""


def _profile_read_policy(*, delisting: bool) -> str:
    return (
        "CREATE POLICY repository_read ON repository_profile FOR SELECT USING ("
        f"tenant_id = {_REQUESTED} "
        "AND EXISTS ("
        + _published_repository(delisting=delisting).format(id="repository_profile.tenant_id")
        + ") "
        "AND (visibility = 'public' "
        f"OR EXISTS ({_GRANT.format(id='repository_profile.tenant_id')})))"
    )


def _insert_policy(*, delisting: bool) -> str:
    return (
        "CREATE POLICY repository_subscription_grant ON repository_subscription FOR INSERT "
        "WITH CHECK ("
        f"(repository_tenant_id = {_CURRENT_TENANT} AND source = 'invited') "
        f"OR (subscriber_tenant_id = {_CURRENT_TENANT} AND source = 'public' "
        "AND EXISTS ("
        + _published_repository(delisting=delisting).format(id=_SUBSCRIBED_REPOSITORY)
        + ") "
        "AND EXISTS (SELECT 1 FROM repository_profile p "
        f"WHERE p.tenant_id = {_SUBSCRIBED_REPOSITORY} "
        "AND p.visibility = 'public')))"
    )


def _discover_policy(*, delisting: bool) -> str:
    return (
        "CREATE POLICY discover_read ON repository_profile FOR SELECT USING ("
        "visibility = 'public' AND release_label IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM tenant t WHERE t.id = repository_profile.tenant_id "
        f"AND t.kind = 'repository' AND {_open(delisting=delisting)}))"
    )


def upgrade() -> None:
    op.add_column("tenant", sa.Column("delisted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenant", sa.Column("delisted_by", sa.UUID(), nullable=True))
    op.add_column("tenant", sa.Column("delist_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "tenant_delisted_by_fkey",
        "tenant",
        "app_user",
        ["delisted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    # Delisted or not as a whole: a repository with a time and a reason of 1 to 500 characters, or
    # nothing. The operator's account may be gone (SET NULL); the time and the reason are kept.
    op.create_check_constraint(
        "tenant_delisted",
        "tenant",
        "(delisted_at IS NULL AND delisted_by IS NULL AND delist_reason IS NULL) "
        "OR (kind = 'repository' AND delisted_at IS NOT NULL AND delist_reason IS NOT NULL "
        "AND char_length(delist_reason) BETWEEN 1 AND 500)",
    )
    op.create_index(
        "ix_tenant_delisted_at",
        "tenant",
        ["delisted_at"],
        postgresql_where=sa.text("delisted_at IS NOT NULL"),
    )
    op.create_index(
        "ix_tenant_delisted_by",
        "tenant",
        ["delisted_by"],
        postgresql_where=sa.text("delisted_by IS NOT NULL"),
    )

    op.execute(_read_tenant_function(delisting=True))
    op.execute("DROP POLICY repository_read ON repository_profile")
    op.execute(_profile_read_policy(delisting=True))
    op.execute("DROP POLICY discover_read ON repository_profile")
    op.execute(_discover_policy(delisting=True))
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(_insert_policy(delisting=True))


def downgrade() -> None:
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(_insert_policy(delisting=False))
    op.execute("DROP POLICY discover_read ON repository_profile")
    op.execute(_discover_policy(delisting=False))
    op.execute("DROP POLICY repository_read ON repository_profile")
    op.execute(_profile_read_policy(delisting=False))
    op.execute(_read_tenant_function(delisting=False))

    op.drop_index("ix_tenant_delisted_by", table_name="tenant")
    op.drop_index("ix_tenant_delisted_at", table_name="tenant")
    op.drop_constraint("tenant_delisted", "tenant")
    op.drop_constraint("tenant_delisted_by_fkey", "tenant")
    op.drop_column("tenant", "delist_reason")
    op.drop_column("tenant", "delisted_by")
    op.drop_column("tenant", "delisted_at")
