"""create v_item and v_item_instance views

Revision ID: 6c2f0a9d3e17
Revises: 1df927764baa
Create Date: 2026-09-08 19:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "6c2f0a9d3e17"
down_revision: str | None = "1df927764baa"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# name -> (value column, alias) for every entity_stat this view surfaces by
# stat_definition.name - see ADR 0019. Each resolves through
# entity_stat.stat_definition_id to one specific, already-tenant-scoped
# stat_definition row, so filtering that joined row by name doesn't need an
# extra tenant check of its own.
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


def _create_view(name: str, source_table: str, extra_select: str = "") -> str:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in _BOOL_STATS]
    )
    joins = "\n".join(
        [_stat_join(stat, "value_int") for stat in _INT_STATS]
        + [_stat_join(stat, "value_bool") for stat in _BOOL_STATS]
    )
    # security_invoker: Postgres views run with the view owner's privileges
    # by default, not the querying role's - without this, RLS on the
    # underlying tables would be silently bypassed through this view even
    # once the app's DB role stops being a superuser (ADR 0002/0012/0019).
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
        {joins}
        """


def upgrade() -> None:
    # Two views, not one covering both tables: "find all base items" and
    # "find all item instances" (e.g. what a character owns) are genuinely
    # different queries, and a single merged view gives no way to tell
    # which table a given row actually came from without joining item/
    # item_instance back in anyway - defeating the point of the view.
    op.execute(_create_view("v_item", "item"))
    op.execute(_create_view("v_item_instance", "item_instance", ", st.owner_entity_id"))


def downgrade() -> None:
    op.execute("DROP VIEW v_item_instance")
    op.execute("DROP VIEW v_item")
