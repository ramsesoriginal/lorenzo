"""containment quantity/stacking, surfaced through v_item/v_item_instance

Revision ID: be4697cb8b60
Revises: 4768ec40991a
Create Date: 2026-09-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "be4697cb8b60"
down_revision: str | None = "4768ec40991a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Unchanged from 4768ec40991a (ADR 0039) - only the two views' own SELECT
# list changes in this migration (one more plain column, `quantity`), not
# the resolution mechanism these describe.
_INT_STATS = ("weight", "height", "price", "rarity", "hp", "armor")
_BOOL_STATS = ("is_magical", "is_cursed")


def _resolved_stat_join(name: str, value_column: str) -> str:
    return (
        f"LEFT JOIN (\n"
        f"    SELECT ves.entity_id, ves.{value_column}\n"
        f"    FROM v_effective_stat ves\n"
        f"    JOIN stat_definition sd ON sd.id = ves.stat_definition_id\n"
        f"    WHERE sd.name = '{name}'\n"
        f") {name} ON {name}.entity_id = e.id"
    )


def _create_view(
    name: str, source_table: str, *, extra_select: str = "", extra_join: str = ""
) -> str:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in _BOOL_STATS]
    )
    joins = "\n".join(
        [_resolved_stat_join(stat, "value_int") for stat in _INT_STATS]
        + [_resolved_stat_join(stat, "value_bool") for stat in _BOOL_STATS]
    )
    # ADR 0041: containment.quantity added to the SELECT list only -
    # containment is already LEFT JOINed here for container_entity_id, no
    # new join needed. NULL exactly when container_entity_id is NULL
    # (uncontained - no stack concept applies), otherwise the containment
    # row's own quantity (NOT NULL DEFAULT 1 at the table level, so always
    # >= 1 whenever a row exists at all).
    return f"""
        CREATE VIEW {name} WITH (security_invoker = true) AS
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id{extra_select},
            description_info.id AS description_id,
            description_info.title AS title,
            {select_columns},
            containment.parent_entity_id AS container_entity_id,
            containment.quantity AS quantity
        FROM entity e
        JOIN {source_table} st ON st.entity_id = e.id
        LEFT JOIN information description_info
            ON description_info.entity_id = e.id AND description_info.type = 'description'
        LEFT JOIN containment ON containment.child_entity_id = e.id
        {extra_join}
        {joins}
        """


def upgrade() -> None:
    # Dependents first (v_item_instance before v_item, matching every prior
    # migration's own order), then the new column + constraint, then
    # recreate both views selecting it.
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
    op.add_column(
        "containment",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_check_constraint("containment_quantity_positive", "containment", "quantity >= 1")
    op.execute(_create_view("v_item", "item"))
    op.execute(
        _create_view(
            "v_item_instance",
            "item_instance",
            extra_select=", ownership.owner_character_id AS owner_entity_id",
            extra_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )


# --- Pre-quantity view SQL, as be4697cb8b60's predecessor (4768ec40991a)
# left it - inlined here rather than imported from that migration, so this
# migration stays a self-contained snapshot downgrade can always replay
# even if a future change edits or removes that file's own helpers.
def _pre_quantity_resolved_stat_join(name: str, value_column: str) -> str:
    return (
        f"LEFT JOIN (\n"
        f"    SELECT ves.entity_id, ves.{value_column}\n"
        f"    FROM v_effective_stat ves\n"
        f"    JOIN stat_definition sd ON sd.id = ves.stat_definition_id\n"
        f"    WHERE sd.name = '{name}'\n"
        f") {name} ON {name}.entity_id = e.id"
    )


def _pre_quantity_create_view(
    name: str, source_table: str, *, extra_select: str = "", extra_join: str = ""
) -> str:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in _BOOL_STATS]
    )
    joins = "\n".join(
        [_pre_quantity_resolved_stat_join(stat, "value_int") for stat in _INT_STATS]
        + [_pre_quantity_resolved_stat_join(stat, "value_bool") for stat in _BOOL_STATS]
    )
    return f"""
        CREATE VIEW {name} WITH (security_invoker = true) AS
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id{extra_select},
            description_info.id AS description_id,
            description_info.title AS title,
            {select_columns},
            containment.parent_entity_id AS container_entity_id
        FROM entity e
        JOIN {source_table} st ON st.entity_id = e.id
        LEFT JOIN information description_info
            ON description_info.entity_id = e.id AND description_info.type = 'description'
        LEFT JOIN containment ON containment.child_entity_id = e.id
        {extra_join}
        {joins}
        """


def downgrade() -> None:
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
    op.drop_constraint("containment_quantity_positive", "containment", type_="check")
    op.drop_column("containment", "quantity")
    op.execute(_pre_quantity_create_view("v_item", "item"))
    op.execute(
        _pre_quantity_create_view(
            "v_item_instance",
            "item_instance",
            extra_select=", ownership.owner_character_id AS owner_entity_id",
            extra_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )
