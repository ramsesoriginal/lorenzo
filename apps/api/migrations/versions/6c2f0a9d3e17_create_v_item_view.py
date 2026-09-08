"""create v_item view

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


def upgrade() -> None:
    select_columns = ", ".join(
        [f"{name}.value_int AS {name}" for name in _INT_STATS]
        + [f"{name}.value_bool AS {name}" for name in _BOOL_STATS]
    )
    joins = "\n".join(
        [_stat_join(name, "value_int") for name in _INT_STATS]
        + [_stat_join(name, "value_bool") for name in _BOOL_STATS]
    )
    # security_invoker: Postgres views run with the view owner's privileges
    # by default, not the querying role's - without this, RLS on the
    # underlying tables would be silently bypassed through this view even
    # once the app's DB role stops being a superuser (ADR 0002/0012/0019).
    op.execute(
        f"""
        CREATE VIEW v_item WITH (security_invoker = true) AS
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id,
            description_info.id AS description_id,
            description_info.title AS title,
            {select_columns},
            containment.parent_entity_id AS container_entity_id
        FROM entity e
        LEFT JOIN information description_info
            ON description_info.entity_id = e.id AND description_info.type = 'description'
        LEFT JOIN containment ON containment.child_entity_id = e.id
        {joins}
        WHERE e.id IN (SELECT entity_id FROM item UNION SELECT entity_id FROM item_instance)
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW v_item")
