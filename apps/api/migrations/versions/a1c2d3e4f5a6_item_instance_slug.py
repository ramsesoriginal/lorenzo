"""item_instance.slug, plus v_item_instance exposing it

Revision ID: a1c2d3e4f5a6
Revises: be4697cb8b60
Create Date: 2026-09-16 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c2d3e4f5a6"
down_revision: str | None = "be4697cb8b60"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Unchanged from be4697cb8b60 (ADR 0041) - only v_item_instance's own SELECT
# list changes in this migration (one more plain column, `slug`, item
# instances only - v_item's own SQL is untouched), not the resolution
# mechanism these describe.
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
    # v_item_instance depends on item_instance.slug, so drop it before
    # adding the column, same "dependents first" order every prior view
    # migration in this file's own lineage already follows - v_item itself
    # is untouched (slug is instance-only), so it doesn't need dropping.
    op.execute("DROP VIEW v_item_instance")
    op.add_column("item_instance", sa.Column("slug", sa.Text(), nullable=True))
    # Partial unique index, not a plain UniqueConstraint - slug is optional,
    # and Postgres already treats every NULL as distinct from every other
    # NULL in an ordinary unique index (see ADR 0028's identical reasoning
    # for `knowledge`'s own two UniqueConstraints), but a *tenant-scoped*
    # uniqueness rule needs the tenant_id column in the index regardless -
    # a plain UniqueConstraint(slug) alone would be tenant-wide, not
    # per-tenant. WHERE slug IS NOT NULL is belt-and-suspenders on top of
    # that NULL-distinctness for readability, not strictly required by it.
    op.create_index(
        "ix_item_instance_tenant_id_slug",
        "item_instance",
        ["tenant_id", "slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )
    op.execute(
        _create_view(
            "v_item_instance",
            "item_instance",
            extra_select=(
                ", ownership.owner_character_id AS owner_entity_id, st.slug AS slug"
            ),
            extra_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )


def downgrade() -> None:
    op.execute("DROP VIEW v_item_instance")
    op.drop_index("ix_item_instance_tenant_id_slug", table_name="item_instance")
    op.drop_column("item_instance", "slug")
    op.execute(
        _create_view(
            "v_item_instance",
            "item_instance",
            extra_select=", ownership.owner_character_id AS owner_entity_id",
            extra_join="LEFT JOIN ownership ON ownership.owned_entity_id = e.id",
        )
    )
