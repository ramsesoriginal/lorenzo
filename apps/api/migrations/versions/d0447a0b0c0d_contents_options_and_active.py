"""options of a contents formula, and the `active` switch of an item instance (ADR 0447)

A contents formula gains `aggregate` (`sum`, `min`, `max`, `count`), `only_active`, `only_kind`, a
`where` stat of the held thing and `if_none`, each with the default that is the formula's
behaviour before: `sum`, every held thing, any kind, no filter. `count` ignores the stat, so the
source may be empty for it and only for it. An item instance gains `active` (true), an item
`starts_inactive` (false), and `v_item_instance` exposes `active`; a view can only gain a column at
the end, so it is replaced with the same query and the new column last.

Revision ID: d0447a0b0c0d
Revises: d0446a0b0c0d
Create Date: 2026-11-11 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0447a0b0c0d"
down_revision: str | None = "d0446a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_VIEW_BODY = """
    SELECT e.id AS entity_id,
        e.tenant_id,
        ownership.owner_character_id AS owner_entity_id,
        entity_slug.slug,
        description_info.id AS description_id,
        description_info.title,
        stats.weight,
        stats.height,
        stats.price,
        stats.rarity,
        stats.hp,
        stats.armor,
        containment.parent_entity_id AS container_entity_id,
        containment.quantity{extra}
       FROM entity e
         JOIN item_instance st ON st.entity_id = e.id
         LEFT JOIN information description_info ON description_info.entity_id = e.id
           AND description_info.type = 'description'
         LEFT JOIN containment ON containment.child_entity_id = e.id
         LEFT JOIN ownership ON ownership.owned_entity_id = e.id
         LEFT JOIN entity_slug ON entity_slug.entity_id = e.id
         LEFT JOIN LATERAL ( SELECT
                max(ves.value_int) FILTER (WHERE sd.name = 'weight') AS weight,
                max(ves.value_int) FILTER (WHERE sd.name = 'height') AS height,
                max(ves.value_int) FILTER (WHERE sd.name = 'price') AS price,
                max(ves.value_int) FILTER (WHERE sd.name = 'rarity') AS rarity,
                max(ves.value_int) FILTER (WHERE sd.name = 'hp') AS hp,
                max(ves.value_int) FILTER (WHERE sd.name = 'armor') AS armor
               FROM v_effective_stat ves
                 JOIN stat_definition sd ON sd.id = ves.stat_definition_id
              WHERE ves.entity_id = e.id
                AND sd.name = ANY (ARRAY['weight', 'height', 'price', 'rarity', 'hp', 'armor'])
             ) stats ON true
"""


def upgrade() -> None:
    op.add_column(
        "item_instance",
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "item",
        sa.Column("starts_inactive", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "computed_stat_contents",
        sa.Column("aggregate", sa.Text(), server_default=sa.text("'sum'"), nullable=False),
    )
    op.add_column(
        "computed_stat_contents",
        sa.Column("only_active", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("computed_stat_contents", sa.Column("only_kind", sa.Text(), nullable=True))
    op.add_column(
        "computed_stat_contents",
        sa.Column("where_stat_definition_id", sa.UUID(), nullable=True),
    )
    op.add_column("computed_stat_contents", sa.Column("if_none", sa.Numeric(), nullable=True))
    op.alter_column("computed_stat_contents", "source_stat_definition_id", nullable=True)
    op.create_foreign_key(
        "computed_stat_contents_where_stat_definition_id_fkey",
        "computed_stat_contents",
        "stat_definition",
        ["where_stat_definition_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_index(
        "ix_computed_stat_contents_where_stat_definition_id",
        "computed_stat_contents",
        ["where_stat_definition_id"],
    )
    op.create_check_constraint(
        "computed_stat_contents_aggregate",
        "computed_stat_contents",
        "aggregate IN ('sum', 'min', 'max', 'count')",
    )
    op.create_check_constraint(
        "computed_stat_contents_only_kind",
        "computed_stat_contents",
        "only_kind IS NULL OR only_kind IN ('item_instance')",
    )
    op.create_check_constraint(
        "computed_stat_contents_source_unless_count",
        "computed_stat_contents",
        "aggregate = 'count' OR source_stat_definition_id IS NOT NULL",
    )
    op.create_check_constraint(
        "computed_stat_contents_if_none_for_min_max",
        "computed_stat_contents",
        "if_none IS NULL OR aggregate IN ('min', 'max')",
    )
    op.execute(
        "CREATE OR REPLACE VIEW v_item_instance WITH (security_invoker = true) AS "
        + _VIEW_BODY.format(extra=",\n        st.active AS active")
    )


def downgrade() -> None:
    op.execute("DROP VIEW v_item_instance")
    op.execute(
        "CREATE VIEW v_item_instance WITH (security_invoker = true) AS "
        + _VIEW_BODY.format(extra="")
    )
    for name in (
        "computed_stat_contents_if_none_for_min_max",
        "computed_stat_contents_source_unless_count",
        "computed_stat_contents_only_kind",
        "computed_stat_contents_aggregate",
    ):
        op.drop_constraint(name, "computed_stat_contents", type_="check")
    op.drop_index(
        "ix_computed_stat_contents_where_stat_definition_id", table_name="computed_stat_contents"
    )
    op.drop_constraint(
        "computed_stat_contents_where_stat_definition_id_fkey",
        "computed_stat_contents",
        type_="foreignkey",
    )
    op.alter_column("computed_stat_contents", "source_stat_definition_id", nullable=False)
    for column in ("if_none", "where_stat_definition_id", "only_kind", "only_active", "aggregate"):
        op.drop_column("computed_stat_contents", column)
    op.drop_column("item", "starts_inactive")
    op.drop_column("item_instance", "active")
