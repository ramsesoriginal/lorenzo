"""tenant.kind and tenant.published_at: repository tenants (ADR 0118)

A tenant is either for play (the default, every existing tenant) or a
repository (RFC 0024). The kind can never change - publishing always
means creating a new tenant, so a live play tenant can't be relabelled -
and a repository holds no campaigns, so no players, GM grants, or invite
links either. Both are enforced here, not only in the routers.

published_at is null while a repository is a draft; only a repository can
be published.

Revision ID: 55377d4b1e58
Revises: ff45d1674cb8
Create Date: 2026-09-25 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "55377d4b1e58"
down_revision: str | None = "ff45d1674cb8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT_KIND = sa.Enum("play", "repository", name="tenant_kind")

# Separate op.execute() calls for each statement - asyncpg prepares every
# statement it sends, and one prepared statement can't hold two commands.
_KIND_IMMUTABLE_FUNCTION = """
CREATE FUNCTION tenant_kind_immutable() RETURNS trigger AS $$
BEGIN
    IF NEW.kind IS DISTINCT FROM OLD.kind THEN
        RAISE EXCEPTION 'tenant.kind can''t change (tenant %)', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
_KIND_IMMUTABLE_TRIGGER = """
CREATE TRIGGER tenant_kind_immutable_trigger
    BEFORE UPDATE OF kind ON tenant
    FOR EACH ROW EXECUTE FUNCTION tenant_kind_immutable();
"""
_NO_CAMPAIGN_FUNCTION = """
CREATE FUNCTION campaign_not_in_repository() RETURNS trigger AS $$
BEGIN
    IF (SELECT kind FROM tenant WHERE id = NEW.tenant_id) = 'repository' THEN
        RAISE EXCEPTION 'a repository holds no campaigns (tenant %)', NEW.tenant_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
_NO_CAMPAIGN_TRIGGER = """
CREATE TRIGGER campaign_not_in_repository_trigger
    BEFORE INSERT OR UPDATE OF tenant_id ON campaign
    FOR EACH ROW EXECUTE FUNCTION campaign_not_in_repository();
"""


def upgrade() -> None:
    _TENANT_KIND.create(op.get_bind())
    op.add_column(
        "tenant",
        sa.Column("kind", _TENANT_KIND, server_default="play", nullable=False),
    )
    op.add_column("tenant", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "tenant_only_repositories_publish",
        "tenant",
        "kind = 'repository' OR published_at IS NULL",
    )
    op.execute(_KIND_IMMUTABLE_FUNCTION)
    op.execute(_KIND_IMMUTABLE_TRIGGER)
    op.execute(_NO_CAMPAIGN_FUNCTION)
    op.execute(_NO_CAMPAIGN_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER campaign_not_in_repository_trigger ON campaign")
    op.execute("DROP FUNCTION campaign_not_in_repository()")
    op.execute("DROP TRIGGER tenant_kind_immutable_trigger ON tenant")
    op.execute("DROP FUNCTION tenant_kind_immutable()")
    op.drop_constraint("tenant_only_repositories_publish", "tenant")
    op.drop_column("tenant", "published_at")
    op.drop_column("tenant", "kind")
    _TENANT_KIND.drop(op.get_bind())
