"""repository_subscription and the gated repository read (ADR 0118)

A repository's owner grants another tenant access with a
repository_subscription row. A granted tenant can then read the
repository's content - but only inside a request that asked to, by setting
the transaction-local app.repository_tenant_id, and only while the
repository is published. Each content table gains a FOR SELECT policy for
that beside tenant_isolation; writes still go through tenant_isolation
alone, so a repository's rows can never be written from outside it.

An ordinary request never sets app.repository_tenant_id, so queries that
rely on RLS alone to scope themselves (v_effective_stat, the prototype
cycle trigger) never see a repository's rows (RFC 0024 amendment A1).

Revision ID: 256f70954d9a
Revises: 55377d4b1e58
Create Date: 2026-09-25 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "256f70954d9a"
down_revision: str | None = "55377d4b1e58"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Every table that can hold a repository's own content, as of this
# revision (RFC 0024 §4 and amendment A3). lorenzo_api.repository_access
# keeps the live list, and a test holds it against the database.
_CONTENT_TABLES = [
    "entity",
    "item",
    "item_instance",
    "being",
    "character",
    "entity_prototype",
    "entity_slug",
    "stat_group",
    "stat_definition",
    "stat_definition_enum_value",
    "entity_stat_group",
    "entity_stat",
    "computed_stat",
    "computed_stat_linear",
    "computed_stat_comparison",
    "containment",
    "ownership",
    "group_member",
    "information",
    "payload",
    "payload_description",
    "payload_number",
    "payload_picture",
    "payload_document",
    "knowledge",
    "content_reference",
]

_CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

_TARGET_IS_REPOSITORY_FUNCTION = """
CREATE FUNCTION repository_subscription_target_is_repository() RETURNS trigger AS $$
BEGIN
    IF (SELECT kind FROM tenant WHERE id = NEW.repository_tenant_id) IS DISTINCT FROM 'repository'
    THEN
        RAISE EXCEPTION 'only a repository can be subscribed to (tenant %)',
            NEW.repository_tenant_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
_TARGET_IS_REPOSITORY_TRIGGER = """
CREATE TRIGGER repository_subscription_target_is_repository_trigger
    BEFORE INSERT OR UPDATE ON repository_subscription
    FOR EACH ROW EXECUTE FUNCTION repository_subscription_target_is_repository();
"""

# The whole rule in one place: the repository this request asked to read,
# if the current tenant holds a grant for it and it's published; otherwise
# null, which no row's tenant_id equals.
_READ_TENANT_FUNCTION = f"""
CREATE FUNCTION repository_read_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT s.repository_tenant_id
    FROM repository_subscription s
    JOIN tenant t ON t.id = s.repository_tenant_id
    WHERE s.repository_tenant_id
            = NULLIF(current_setting('app.repository_tenant_id', true), '')::uuid
      AND s.subscriber_tenant_id = {_CURRENT_TENANT}
      AND t.kind = 'repository'
      AND t.published_at IS NOT NULL
$$;
"""


def upgrade() -> None:
    op.create_table(
        "repository_subscription",
        sa.Column("repository_tenant_id", sa.UUID(), nullable=False),
        sa.Column("subscriber_tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["repository_tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscriber_tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("repository_tenant_id", "subscriber_tenant_id"),
        sa.CheckConstraint(
            "repository_tenant_id <> subscriber_tenant_id",
            name="repository_subscription_not_self",
        ),
    )
    op.create_index(
        "ix_repository_subscription_subscriber_tenant_id",
        "repository_subscription",
        ["subscriber_tenant_id"],
    )
    op.create_index(
        "ix_repository_subscription_created_by", "repository_subscription", ["created_by"]
    )
    op.execute(_TARGET_IS_REPOSITORY_FUNCTION)
    op.execute(_TARGET_IS_REPOSITORY_TRIGGER)

    # Either side reads a grant; only the repository's side creates one;
    # either side removes it. Nothing updates one.
    op.execute("ALTER TABLE repository_subscription ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE repository_subscription FORCE ROW LEVEL SECURITY")
    either_side = (
        f"repository_tenant_id = {_CURRENT_TENANT} OR subscriber_tenant_id = {_CURRENT_TENANT}"
    )
    op.execute(
        "CREATE POLICY repository_subscription_read ON repository_subscription "
        f"FOR SELECT USING ({either_side})"
    )
    op.execute(
        "CREATE POLICY repository_subscription_grant ON repository_subscription "
        f"FOR INSERT WITH CHECK (repository_tenant_id = {_CURRENT_TENANT})"
    )
    op.execute(
        "CREATE POLICY repository_subscription_remove ON repository_subscription "
        f"FOR DELETE USING ({either_side})"
    )

    op.execute(_READ_TENANT_FUNCTION)
    for table in _CONTENT_TABLES:
        # (SELECT ...) makes it an init plan: run once per query, not per row.
        op.execute(
            f'CREATE POLICY repository_read ON "{table}" FOR SELECT '
            "USING (tenant_id = (SELECT repository_read_tenant_id()))"
        )


def downgrade() -> None:
    for table in _CONTENT_TABLES:
        op.execute(f'DROP POLICY repository_read ON "{table}"')
    op.execute("DROP FUNCTION repository_read_tenant_id()")
    op.drop_table("repository_subscription")
    op.execute("DROP FUNCTION repository_subscription_target_is_repository()")
