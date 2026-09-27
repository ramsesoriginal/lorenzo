"""retire is_magical and is_cursed from v_item and v_item_instance (ADR 0129)

The two views stop hardcoding the two boolean stats by name. Tenants keep
their own stat definitions and values; they're read like any other tag.
Only the views change, so there's no data to move either way.

Revision ID: c3a9e1d5b7f2
Revises: f72e45aaddb9
Create Date: 2026-09-27 19:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3a9e1d5b7f2"
down_revision: str | None = "f72e45aaddb9"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Both views as be4697cb8b60 (v_item) and 22b8aef660db (v_item_instance) left
# them, inlined so this migration stays a self-contained snapshot. Only the
# boolean columns differ between upgrade and downgrade.
_INT_STATS = ("weight", "height", "price", "rarity", "hp", "armor")
_RETIRED_BOOL_STATS = ("is_magical", "is_cursed")


def _resolved_stat_join(name: str, value_column: str) -> str:
    return (
        f"LEFT JOIN (\n"
        f"    SELECT ves.entity_id, ves.{value_column}\n"
        f"    FROM v_effective_stat ves\n"
        f"    JOIN stat_definition sd ON sd.id = ves.stat_definition_id\n"
        f"    WHERE sd.name = '{name}'\n"
        f") {name} ON {name}.entity_id = e.id"
    )


def _stat_columns(bool_stats: Sequence[str]) -> tuple[str, str]:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in bool_stats]
    )
    joins = "\n".join(
        [_resolved_stat_join(stat, "value_int") for stat in _INT_STATS]
        + [_resolved_stat_join(stat, "value_bool") for stat in bool_stats]
    )
    return select_columns, joins


def _item_view(bool_stats: Sequence[str]) -> str:
    select_columns, joins = _stat_columns(bool_stats)
    return f"""
        CREATE VIEW v_item WITH (security_invoker = true) AS
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id,
            description_info.id AS description_id,
            description_info.title AS title,
            {select_columns},
            containment.parent_entity_id AS container_entity_id,
            containment.quantity AS quantity
        FROM entity e
        JOIN item st ON st.entity_id = e.id
        LEFT JOIN information description_info
            ON description_info.entity_id = e.id AND description_info.type = 'description'
        LEFT JOIN containment ON containment.child_entity_id = e.id
        {joins}
        """


def _item_instance_view(bool_stats: Sequence[str]) -> str:
    select_columns, joins = _stat_columns(bool_stats)
    return f"""
        CREATE VIEW v_item_instance WITH (security_invoker = true) AS
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id,
            ownership.owner_character_id AS owner_entity_id,
            entity_slug.slug AS slug,
            description_info.id AS description_id,
            description_info.title AS title,
            {select_columns},
            containment.parent_entity_id AS container_entity_id,
            containment.quantity AS quantity
        FROM entity e
        JOIN item_instance st ON st.entity_id = e.id
        LEFT JOIN information description_info
            ON description_info.entity_id = e.id AND description_info.type = 'description'
        LEFT JOIN containment ON containment.child_entity_id = e.id
        LEFT JOIN ownership ON ownership.owned_entity_id = e.id
        LEFT JOIN entity_slug ON entity_slug.entity_id = e.id
        {joins}
        """


def _recreate(bool_stats: Sequence[str]) -> None:
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
    op.execute(_item_view(bool_stats))
    op.execute(_item_instance_view(bool_stats))


def upgrade() -> None:
    _recreate(())


def downgrade() -> None:
    _recreate(_RETIRED_BOOL_STATS)
