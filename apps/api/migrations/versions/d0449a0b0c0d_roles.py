"""roles: what the API reads a stat or a stat group as, by role and not by name (ADR 0449)

`stat_definition.role` and `stat_group.role`, each from a closed list, unique in a library where
set. Every existing definition and group with a role's name gets that role, whatever its type, so
each read answers as it did; `v_item` and `v_item_instance` read the named columns by role. A view
cannot lose a column and keep its dependents, so each is replaced with the same query and the
role where the name was.

Revision ID: d0449a0b0c0d
Revises: d0448a0b0c0d
Create Date: 2026-11-12 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0449a0b0c0d"
down_revision: str | None = "d0448a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_DEFINITION_ROLES = (
    "weight",
    "height",
    "price",
    "rarity",
    "hp",
    "armor",
    "size",
    "carry_capacity",
    "containment_capacity",
    "max_item_size",
    "binding",
    "is_container",
)
_GROUP_ROLES = ("physical", "economic", "destroyable", "damaging", "tags")


def _listed(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# The stat columns of the two item views, keyed by `column` (name or role).
def _views(key: str, *, extra_instance: str) -> tuple[str, str]:
    lateral = f"""
         LEFT JOIN LATERAL ( SELECT
                max(ves.value_int) FILTER (WHERE sd.{key} = 'weight') AS weight,
                max(ves.value_int) FILTER (WHERE sd.{key} = 'height') AS height,
                max(ves.value_int) FILTER (WHERE sd.{key} = 'price') AS price,
                max(ves.value_int) FILTER (WHERE sd.{key} = 'rarity') AS rarity,
                max(ves.value_int) FILTER (WHERE sd.{key} = 'hp') AS hp,
                max(ves.value_int) FILTER (WHERE sd.{key} = 'armor') AS armor
               FROM v_effective_stat ves
                 JOIN stat_definition sd ON sd.id = ves.stat_definition_id
              WHERE ves.entity_id = e.id
                AND sd.{key} = ANY (ARRAY['weight', 'height', 'price', 'rarity', 'hp', 'armor'])
             ) stats ON true
    """
    item = f"""
    SELECT e.id AS entity_id,
        e.tenant_id,
        description_info.id AS description_id,
        description_info.title,
        stats.weight,
        stats.height,
        stats.price,
        stats.rarity,
        stats.hp,
        stats.armor,
        containment.parent_entity_id AS container_entity_id,
        containment.quantity
       FROM entity e
         JOIN item st ON st.entity_id = e.id
         LEFT JOIN information description_info ON description_info.entity_id = e.id
           AND description_info.type = 'description'
         LEFT JOIN containment ON containment.child_entity_id = e.id{lateral}
    """
    instance = f"""
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
        containment.quantity{extra_instance}
       FROM entity e
         JOIN item_instance st ON st.entity_id = e.id
         LEFT JOIN information description_info ON description_info.entity_id = e.id
           AND description_info.type = 'description'
         LEFT JOIN containment ON containment.child_entity_id = e.id
         LEFT JOIN ownership ON ownership.owned_entity_id = e.id
         LEFT JOIN entity_slug ON entity_slug.entity_id = e.id{lateral}
    """
    return item, instance


def _replace_views(key: str) -> None:
    item, instance = _views(key, extra_instance=",\n        st.active AS active")
    op.execute(f"CREATE OR REPLACE VIEW v_item WITH (security_invoker = true) AS {item}")
    op.execute(
        f"CREATE OR REPLACE VIEW v_item_instance WITH (security_invoker = true) AS {instance}"
    )


def upgrade() -> None:
    op.add_column("stat_definition", sa.Column("role", sa.Text(), nullable=True))
    op.add_column("stat_group", sa.Column("role", sa.Text(), nullable=True))
    # A library's stat that has a role's name has the role, whatever its type.
    op.execute(
        f"UPDATE stat_definition SET role = name WHERE name IN ({_listed(_DEFINITION_ROLES)})"
    )
    op.execute(f"UPDATE stat_group SET role = name WHERE name IN ({_listed(_GROUP_ROLES)})")
    op.create_check_constraint(
        "stat_definition_role",
        "stat_definition",
        f"role IS NULL OR role IN ({_listed(_DEFINITION_ROLES)})",
    )
    op.create_check_constraint(
        "stat_group_role", "stat_group", f"role IS NULL OR role IN ({_listed(_GROUP_ROLES)})"
    )
    op.create_index(
        "stat_definition_tenant_id_role_key",
        "stat_definition",
        ["tenant_id", "role"],
        unique=True,
        postgresql_where=sa.text("role IS NOT NULL"),
    )
    op.create_index(
        "stat_group_tenant_id_role_key",
        "stat_group",
        ["tenant_id", "role"],
        unique=True,
        postgresql_where=sa.text("role IS NOT NULL"),
    )
    _replace_views("role")


def downgrade() -> None:
    _replace_views("name")
    op.drop_index("stat_group_tenant_id_role_key", table_name="stat_group")
    op.drop_index("stat_definition_tenant_id_role_key", table_name="stat_definition")
    op.drop_constraint("stat_group_role", "stat_group", type_="check")
    op.drop_constraint("stat_definition_role", "stat_definition", type_="check")
    op.drop_column("stat_group", "role")
    op.drop_column("stat_definition", "role")
