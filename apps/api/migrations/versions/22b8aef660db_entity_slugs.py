"""entity slugs: entity_slug replaces item_instance.slug

Revision ID: 22b8aef660db
Revises: 5fade6f98352
Create Date: 2026-09-24 23:39:03.424961

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "22b8aef660db"
down_revision: str | None = "5fade6f98352"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# v_item_instance as a1c2d3e4f5a6 (ADR 0043) left it; only where `slug` comes
# from changes here.
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


def _create_item_instance_view(slug_source: str, slug_join: str = "") -> str:
    select_columns = ", ".join(
        [f"{stat}.value_int AS {stat}" for stat in _INT_STATS]
        + [f"{stat}.value_bool AS {stat}" for stat in _BOOL_STATS]
    )
    joins = "\n".join(
        [_resolved_stat_join(stat, "value_int") for stat in _INT_STATS]
        + [_resolved_stat_join(stat, "value_bool") for stat in _BOOL_STATS]
    )
    return f"""
        CREATE VIEW v_item_instance WITH (security_invoker = true) AS
        SELECT
            e.id AS entity_id,
            e.tenant_id AS tenant_id,
            ownership.owner_character_id AS owner_entity_id,
            {slug_source} AS slug,
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
        {slug_join}
        {joins}
        """


def upgrade() -> None:
    op.create_table(
        "entity_slug",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.UniqueConstraint("tenant_id", "slug"),
    )
    op.create_index(op.f("ix_entity_slug_tenant_id"), "entity_slug", ["tenant_id"], unique=False)
    # ADR 0002/0012: ENABLE and FORCE both, so the table owner is bound too.
    op.execute("ALTER TABLE entity_slug ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE entity_slug FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON entity_slug "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    op.execute(
        "INSERT INTO entity_slug (entity_id, tenant_id, slug) "
        "SELECT entity_id, tenant_id, slug FROM item_instance WHERE slug IS NOT NULL"
    )
    # The view reads item_instance.slug, so it goes before the column does.
    op.execute("DROP VIEW v_item_instance")
    op.drop_index("ix_item_instance_tenant_id_slug", table_name="item_instance")
    op.drop_column("item_instance", "slug")
    op.execute(
        _create_item_instance_view(
            "entity_slug.slug", "LEFT JOIN entity_slug ON entity_slug.entity_id = e.id"
        )
    )


def downgrade() -> None:
    op.execute("DROP VIEW v_item_instance")
    op.add_column("item_instance", sa.Column("slug", sa.Text(), nullable=True))
    op.create_index(
        "ix_item_instance_tenant_id_slug",
        "item_instance",
        ["tenant_id", "slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )
    # Item instances get their slugs back; other entities' slugs have nowhere
    # to go and are dropped with the table.
    op.execute(
        "UPDATE item_instance ii SET slug = es.slug "
        "FROM entity_slug es WHERE es.entity_id = ii.entity_id"
    )
    op.execute(_create_item_instance_view("st.slug"))
    op.drop_index(op.f("ix_entity_slug_tenant_id"), table_name="entity_slug")
    op.drop_table("entity_slug")
