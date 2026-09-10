"""player and campaign_gm rls allow self access for GET /tenants

Revision ID: a22dc991a926
Revises: 28b5b7c7772b
Create Date: 2026-09-11 00:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a22dc991a926"
down_revision: str | None = "28b5b7c7772b"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# GET /tenants (ADR 0030/RFC 0003) unions Membership/Player/CampaignGm rows
# to answer "every tenant I belong to in any capacity" - deliberately not
# tenant-scoped, the same shape GET /me already needed for Membership alone
# (8d9ec377f48a). Found empirically: querying Player/CampaignGm here with
# no single app.tenant_id set hit their still-strict single-argument
# policy, which raises (or, on a pooled connection previously used for a
# real tenant-scoped request, fails a uuid cast on '' rather than NULL -
# same NULLIF gotcha as membership's own fix). Same NULLIF(...,
# '')::uuid shape, same reasoning, extended to the two tables that turned
# out to need it too.
_TABLES = ("player", "campaign_gm")
_NEW_USING = (
    "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid "
    "OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
)
_OLD_USING = "tenant_id = current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER POLICY tenant_isolation ON {table} USING ({_NEW_USING})")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER POLICY tenant_isolation ON {table} USING ({_OLD_USING})")
