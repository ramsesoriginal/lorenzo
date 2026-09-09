"""create being, character_player, ownership tables

Revision ID: 91d78aeb6caf
Revises: 0e2ac3f5758d
Create Date: 2026-09-09 03:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "91d78aeb6caf"
down_revision: str | None = "0e2ac3f5758d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT_SCOPED_TABLES = ("being", "character_player", "ownership")

# Same stat-join shape as 6c2f0a9d3e17_create_v_item_view.py, reconstructed
# here rather than imported - migrations are standalone, addressed by
# revision, not meant to import each other. Only v_item_instance actually
# changes (owner_entity_id moves from a stored column to a join against
# ownership); v_item's own definition is untouched, so it isn't recreated.
_INT_STATS = ("weight", "height", "price", "rarity", "hp", "armor")
_BOOL_STATS = ("is_magical", "is_cursed")


def _stat_join(name: str, value_column: str) -> str:
    return (
        f"LEFT JOIN (\n"
        f"    SELECT es.entity_id, es.{value_column}\n"
        f"    FROM entity_stat es\n"
        f"    JOIN stat_definition sd ON sd.id = es.stat_definition_id\n"
        f"    WHERE sd.name = '{name}'\n"
        f") {name} ON {name}.entity_id = e.id"
    )


def _v_item_instance_sql(*, owner_select: str, owner_join: str) -> str:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in _BOOL_STATS]
    )
    joins = "\n".join(
        [_stat_join(stat, "value_int") for stat in _INT_STATS]
        + [_stat_join(stat, "value_bool") for stat in _BOOL_STATS]
    )
    return f"""
        CREATE OR REPLACE VIEW v_item_instance WITH (security_invoker = true) AS
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id, {owner_select},
            description_info.id AS description_id,
            description_info.title AS title,
            {select_columns},
            containment.parent_entity_id AS container_entity_id
        FROM entity e
        JOIN item_instance st ON st.entity_id = e.id
        LEFT JOIN information description_info
            ON description_info.entity_id = e.id AND description_info.type = 'description'
        LEFT JOIN containment ON containment.child_entity_id = e.id
        {owner_join}
        {joins}
        """


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "being",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        # Nullable, ON DELETE SET NULL - matching item_instance.owner_entity_id's
        # own precedent (ADR 0019): losing the owning player shouldn't
        # destroy the character, just leave it player-less (an NPC).
        sa.Column("owner_player_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_player_id"], ["player.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_being_tenant_id"), "being", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_being_owner_player_id"), "being", ["owner_player_id"], unique=False)

    op.create_table(
        "character_player",
        sa.Column("character_entity_id", sa.UUID(), nullable=False),
        sa.Column("player_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("character_entity_id", "player_id"),
        sa.ForeignKeyConstraint(["character_entity_id"], ["being.entity_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["player.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_character_player_tenant_id"), "character_player", ["tenant_id"], unique=False
    )

    op.create_table(
        "ownership",
        sa.Column("owned_entity_id", sa.UUID(), nullable=False),
        # Plain FK -> entity.id, not being.entity_id - RFC 0002 is explicit
        # this isn't restricted to characters as an owner at the schema
        # level (a faction or place could own something later); only
        # characters are actually populated in this slice. See ADR 0025.
        sa.Column("owner_character_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("owned_entity_id"),
        sa.ForeignKeyConstraint(["owned_entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_character_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_ownership_tenant_id"), "ownership", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_ownership_owner_character_id"), "ownership", ["owner_character_id"], unique=False
    )

    for table in _TENANT_SCOPED_TABLES:
        _enable_rls(table)

    # Backfill ownership from the placeholder column before dropping it -
    # see ADR 0025.
    op.execute(
        "INSERT INTO ownership (owned_entity_id, owner_character_id, tenant_id) "
        "SELECT entity_id, owner_entity_id, tenant_id FROM item_instance "
        "WHERE owner_entity_id IS NOT NULL"
    )

    # Same column name/position/type in the view's own output as before -
    # VItemInstance/ItemInstanceOut/the /owned-by REST route need no code
    # changes at all (ADR 0025). Must run before dropping the column below:
    # Postgres won't drop a column a view still depends on.
    op.execute(
        _v_item_instance_sql(
            owner_select="ownership.owner_character_id AS owner_entity_id",
            owner_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )
    op.drop_column("item_instance", "owner_entity_id")


def downgrade() -> None:
    op.add_column(
        "item_instance",
        sa.Column("owner_entity_id", postgresql.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "item_instance_owner_entity_id_fkey",
        "item_instance",
        "entity",
        ["owner_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_item_instance_owner_entity_id"),
        "item_instance",
        ["owner_entity_id"],
        unique=False,
    )
    op.execute(
        "UPDATE item_instance SET owner_entity_id = ownership.owner_character_id "
        "FROM ownership WHERE ownership.owned_entity_id = item_instance.entity_id"
    )

    # Must run before dropping `ownership` below: the view's current
    # definition (from upgrade()) still joins against it.
    op.execute(
        _v_item_instance_sql(owner_select="st.owner_entity_id AS owner_entity_id", owner_join="")
    )

    op.drop_table("ownership")
    op.drop_table("character_player")
    op.drop_index(op.f("ix_being_owner_player_id"), table_name="being")
    op.drop_index(op.f("ix_being_tenant_id"), table_name="being")
    op.drop_table("being")
