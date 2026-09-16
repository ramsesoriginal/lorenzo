"""tenant campaign read api schema

Revision ID: 28b5b7c7772b
Revises: 26328784d301
Create Date: 2026-09-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "28b5b7c7772b"
down_revision: str | None = "26328784d301"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Postgres's own default constraint-naming convention (<table>_<col(s)>_key/
# _fkey/_pkey for an unnamed constraint) - matches how app_user's existing
# authgear_subject_id UNIQUE got its name, so a later autogenerate diffing
# these models sees the same names it would have picked itself.
_RENAMED_OPT_OUT_CONSTRAINTS = (
    ("orga_campaign_opt_out_pkey", "tenant_admin_campaign_opt_out_pkey"),
    ("orga_campaign_opt_out_tenant_id_fkey", "tenant_admin_campaign_opt_out_tenant_id_fkey"),
    ("orga_campaign_opt_out_user_id_fkey", "tenant_admin_campaign_opt_out_user_id_fkey"),
    ("orga_campaign_opt_out_campaign_id_fkey", "tenant_admin_campaign_opt_out_campaign_id_fkey"),
)


def upgrade() -> None:
    # tenant: permanent server defaults (ADR 0022's own precedent for
    # `name`, extended to slug/description here) - avoids retrofitting the
    # ~50 existing bare Tenant() fixture calls across the test suite. A
    # random slug is a placeholder, not a real one; a real create-tenant
    # flow (RFC 0012, not built yet) always supplies a derived one
    # explicitly.
    op.add_column(
        "tenant",
        sa.Column(
            "slug", sa.Text(), server_default=sa.text("gen_random_uuid()::text"), nullable=False
        ),
    )
    op.create_unique_constraint("tenant_slug_key", "tenant", ["slug"])
    op.add_column(
        "tenant",
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
    )

    # campaign: temporary defaults only, to backfill the handful of
    # pre-existing rows (this is pre-release - a stray leftover row from an
    # interrupted local test run is the realistic case here, confirmed via
    # the privileged connection before writing this migration). Dropped
    # immediately after: ADR 0030/RFC 0003 wants every future write to
    # supply both explicitly - test fixtures use the new make_campaign()
    # conftest helper instead, not a column default.
    op.add_column(
        "campaign",
        sa.Column(
            "slug", sa.Text(), server_default=sa.text("gen_random_uuid()::text"), nullable=False
        ),
    )
    op.alter_column("campaign", "slug", server_default=None)
    op.add_column(
        "campaign",
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
    )
    op.alter_column("campaign", "description", server_default=None)
    op.create_unique_constraint("campaign_tenant_id_slug_key", "campaign", ["tenant_id", "slug"])

    op.add_column(
        "campaign",
        sa.Column("secret", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # entity_id: added nullable first, backfilled row by row (one dedicated
    # Entity per existing campaign - "trivial pre-release" per RFC 0003's
    # own words), then tightened to NOT NULL - the only way to add a
    # required FK to a table that might already have rows.
    op.add_column("campaign", sa.Column("entity_id", sa.UUID(), nullable=True))
    connection = op.get_bind()
    for campaign_id, tenant_id, name in connection.execute(
        sa.text("SELECT id, tenant_id, name FROM campaign")
    ).fetchall():
        entity_id = connection.execute(
            sa.text("INSERT INTO entity (tenant_id, name) VALUES (:t, :n) RETURNING id"),
            {"t": tenant_id, "n": name},
        ).scalar_one()
        connection.execute(
            sa.text("UPDATE campaign SET entity_id = :e WHERE id = :c"),
            {"e": entity_id, "c": campaign_id},
        )
    op.alter_column("campaign", "entity_id", nullable=False)
    # unique=True: "a dedicated Entity row" (RFC 0003) means exactly one
    # campaign per entity - not asked for explicitly, but follows directly
    # from "dedicated" and costs nothing to enforce.
    op.create_unique_constraint("campaign_entity_id_key", "campaign", ["entity_id"])
    # RESTRICT, not CASCADE (the one deliberate exception on this table):
    # deleting the campaign must explicitly clean up its entity first (RFC
    # 0006, not built yet) - this only actually fires if someone deletes
    # the Entity directly, out of band.
    op.create_foreign_key(
        "campaign_entity_id_fkey",
        "campaign",
        "entity",
        ["entity_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # ADR 0029's attribution pair, landing on campaign now that this slice
    # gives it real read-schema exposure (ADR 0029's own phased table).
    op.add_column("campaign", sa.Column("created_by", sa.UUID(), nullable=True))
    op.add_column("campaign", sa.Column("updated_by", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_campaign_created_by"), "campaign", ["created_by"], unique=False)
    op.create_index(op.f("ix_campaign_updated_by"), "campaign", ["updated_by"], unique=False)
    op.create_foreign_key(
        "campaign_created_by_fkey",
        "campaign",
        "app_user",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "campaign_updated_by_fkey",
        "campaign",
        "app_user",
        ["updated_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # orga_campaign_opt_out -> tenant_admin_campaign_opt_out (ADR 0030/RFC
    # 0003): the opt-out now applies to whichever of OWNER/ORGA the caller
    # holds, not just ORGA, so the old name no longer described what it
    # governs. RENAME preserves the table's RLS policy (tenant_isolation)
    # and data untouched - only the name and its auto-named constraints
    # need updating explicitly.
    op.rename_table("orga_campaign_opt_out", "tenant_admin_campaign_opt_out")
    for old_name, new_name in _RENAMED_OPT_OUT_CONSTRAINTS:
        op.execute(
            f"ALTER TABLE tenant_admin_campaign_opt_out RENAME CONSTRAINT {old_name} TO {new_name}"
        )


def downgrade() -> None:
    for old_name, new_name in _RENAMED_OPT_OUT_CONSTRAINTS:
        op.execute(
            f"ALTER TABLE tenant_admin_campaign_opt_out RENAME CONSTRAINT {new_name} TO {old_name}"
        )
    op.rename_table("tenant_admin_campaign_opt_out", "orga_campaign_opt_out")

    op.drop_constraint("campaign_updated_by_fkey", "campaign", type_="foreignkey")
    op.drop_constraint("campaign_created_by_fkey", "campaign", type_="foreignkey")
    op.drop_index(op.f("ix_campaign_updated_by"), table_name="campaign")
    op.drop_index(op.f("ix_campaign_created_by"), table_name="campaign")
    op.drop_column("campaign", "updated_by")
    op.drop_column("campaign", "created_by")

    op.drop_constraint("campaign_entity_id_fkey", "campaign", type_="foreignkey")
    op.drop_constraint("campaign_entity_id_key", "campaign", type_="unique")
    # The Entity rows the upgrade backfilled aren't deleted here - they
    # become ordinary unattached entities, the same state any entity with
    # nothing else pointing at it is already in. Low-stakes, and this is a
    # data cleanup concern, not a schema-reversal one.
    op.drop_column("campaign", "entity_id")

    op.drop_column("campaign", "secret")

    op.drop_constraint("campaign_tenant_id_slug_key", "campaign", type_="unique")
    op.drop_column("campaign", "description")
    op.drop_column("campaign", "slug")

    op.drop_column("tenant", "description")
    op.drop_constraint("tenant_slug_key", "tenant", type_="unique")
    op.drop_column("tenant", "slug")
