"""same-tenant references: composite (..., tenant_id) foreign keys (ADR 0117)

Every foreign key between two tenant tables becomes composite with
tenant_id, so a row can never point into another tenant - even once RFC
0024's repositories make one tenant's rows readable from another (ADR
0118). A foreign-key check ignores RLS, so until now only the routers'
explicit tenant_id filters kept both ends in one tenant.

Each key keeps its name and its ON DELETE behaviour. Adding it validates
every existing row: a row that already points across tenants makes this
migration fail, naming the constraint, rather than being carried forward.

Revision ID: ff45d1674cb8
Revises: 93647604e820
Create Date: 2026-09-25 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "ff45d1674cb8"
down_revision: str | None = "93647604e820"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# (table, key columns) - each gains UNIQUE (key columns..., tenant_id) for a
# composite key to reference.
_REFERENCED: list[tuple[str, tuple[str, ...]]] = [
    ("entity", ("id",)),
    ("stat_group", ("id",)),
    ("stat_definition", ("id",)),
    ("information", ("id",)),
    ("payload", ("id",)),
    ("being", ("entity_id",)),
    ("character", ("entity_id",)),
    ("campaign", ("id",)),
    ("player", ("id",)),
    ("computed_stat", ("entity_id", "stat_definition_id")),
]

# (table, constraint name, columns, referenced table, referenced columns,
# ON DELETE) - every foreign key whose two tables both carry tenant_id, as
# they stood at 93647604e820. ON DELETE is None where the key had none (NO
# ACTION).
_KEYS: list[tuple[str, str, tuple[str, ...], str, tuple[str, ...], str | None]] = [
    ("being", "being_entity_id_fkey", ("entity_id",), "entity", ("id",), "CASCADE"),
    ("campaign", "campaign_entity_id_fkey", ("entity_id",), "entity", ("id",), "RESTRICT"),
    (
        "campaign_gm",
        "campaign_gm_campaign_id_fkey",
        ("campaign_id",),
        "campaign",
        ("id",),
        "CASCADE",
    ),
    (
        "campaign_invite",
        "campaign_invite_campaign_id_fkey",
        ("campaign_id",),
        "campaign",
        ("id",),
        "CASCADE",
    ),
    (
        "campaign_profile_picture",
        "campaign_profile_picture_campaign_id_fkey",
        ("campaign_id",),
        "campaign",
        ("id",),
        "CASCADE",
    ),
    ("character", "character_entity_id_fkey", ("entity_id",), "being", ("entity_id",), "CASCADE"),
    # The only nulling key: the column list keeps SET NULL from also trying
    # to null tenant_id (PostgreSQL 15+).
    (
        "character",
        "character_owner_player_id_fkey",
        ("owner_player_id",),
        "player",
        ("id",),
        "SET NULL (owner_player_id)",
    ),
    (
        "character_player",
        "character_player_character_entity_id_fkey",
        ("character_entity_id",),
        "character",
        ("entity_id",),
        "CASCADE",
    ),
    (
        "character_player",
        "character_player_player_id_fkey",
        ("player_id",),
        "player",
        ("id",),
        "CASCADE",
    ),
    (
        "computed_stat",
        "computed_stat_entity_id_fkey",
        ("entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "computed_stat",
        "computed_stat_stat_definition_id_fkey",
        ("stat_definition_id",),
        "stat_definition",
        ("id",),
        "CASCADE",
    ),
    (
        "computed_stat_comparison",
        "computed_stat_comparison_entity_id_stat_definition_id_fkey",
        ("entity_id", "stat_definition_id"),
        "computed_stat",
        ("entity_id", "stat_definition_id"),
        "CASCADE",
    ),
    (
        "computed_stat_comparison",
        "computed_stat_comparison_left_stat_definition_id_fkey",
        ("left_stat_definition_id",),
        "stat_definition",
        ("id",),
        None,
    ),
    (
        "computed_stat_comparison",
        "computed_stat_comparison_right_stat_definition_id_fkey",
        ("right_stat_definition_id",),
        "stat_definition",
        ("id",),
        None,
    ),
    (
        "computed_stat_linear",
        "computed_stat_linear_entity_id_stat_definition_id_fkey",
        ("entity_id", "stat_definition_id"),
        "computed_stat",
        ("entity_id", "stat_definition_id"),
        "CASCADE",
    ),
    (
        "computed_stat_linear",
        "computed_stat_linear_source_stat_definition_id_fkey",
        ("source_stat_definition_id",),
        "stat_definition",
        ("id",),
        None,
    ),
    (
        "containment",
        "containment_child_entity_id_fkey",
        ("child_entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "containment",
        "containment_parent_entity_id_fkey",
        ("parent_entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "content_reference",
        "content_reference_payload_id_fkey",
        ("payload_id",),
        "payload",
        ("id",),
        "CASCADE",
    ),
    (
        "entity_prototype",
        "entity_prototype_entity_id_fkey",
        ("entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "entity_prototype",
        "entity_prototype_prototype_id_fkey",
        ("prototype_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    ("entity_slug", "entity_slug_entity_id_fkey", ("entity_id",), "entity", ("id",), "CASCADE"),
    ("entity_stat", "entity_stat_entity_id_fkey", ("entity_id",), "entity", ("id",), "CASCADE"),
    (
        "entity_stat",
        "entity_stat_stat_definition_id_fkey",
        ("stat_definition_id",),
        "stat_definition",
        ("id",),
        "CASCADE",
    ),
    (
        "entity_stat_group",
        "entity_stat_group_entity_id_fkey",
        ("entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "entity_stat_group",
        "entity_stat_group_stat_group_id_fkey",
        ("stat_group_id",),
        "stat_group",
        ("id",),
        "CASCADE",
    ),
    (
        "group_member",
        "group_member_character_entity_id_fkey",
        ("character_entity_id",),
        "character",
        ("entity_id",),
        "CASCADE",
    ),
    (
        "group_member",
        "group_member_group_entity_id_fkey",
        ("group_entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    ("information", "information_entity_id_fkey", ("entity_id",), "entity", ("id",), "CASCADE"),
    ("item", "item_entity_id_fkey", ("entity_id",), "entity", ("id",), "CASCADE"),
    (
        "item_instance",
        "item_instance_entity_id_fkey",
        ("entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "knowledge",
        "knowledge_information_id_fkey",
        ("information_id",),
        "information",
        ("id",),
        "CASCADE",
    ),
    (
        "knowledge",
        "knowledge_knower_entity_id_fkey",
        ("knower_entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "knowledge",
        "knowledge_knower_player_id_fkey",
        ("knower_player_id",),
        "player",
        ("id",),
        "CASCADE",
    ),
    (
        "ownership",
        "ownership_owned_entity_id_fkey",
        ("owned_entity_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "ownership",
        "ownership_owner_character_id_fkey",
        ("owner_character_id",),
        "entity",
        ("id",),
        "CASCADE",
    ),
    (
        "payload",
        "payload_information_id_fkey",
        ("information_id",),
        "information",
        ("id",),
        "CASCADE",
    ),
    (
        "payload_description",
        "payload_description_payload_id_fkey",
        ("payload_id",),
        "payload",
        ("id",),
        "CASCADE",
    ),
    (
        "payload_document",
        "payload_document_payload_id_fkey",
        ("payload_id",),
        "payload",
        ("id",),
        "CASCADE",
    ),
    (
        "payload_number",
        "payload_number_payload_id_fkey",
        ("payload_id",),
        "payload",
        ("id",),
        "CASCADE",
    ),
    (
        "payload_picture",
        "payload_picture_payload_id_fkey",
        ("payload_id",),
        "payload",
        ("id",),
        "CASCADE",
    ),
    ("player", "player_campaign_id_fkey", ("campaign_id",), "campaign", ("id",), "CASCADE"),
    (
        "stat_definition",
        "stat_definition_stat_group_id_fkey",
        ("stat_group_id",),
        "stat_group",
        ("id",),
        "CASCADE",
    ),
    (
        "stat_definition_enum_value",
        "stat_definition_enum_value_stat_definition_id_fkey",
        ("stat_definition_id",),
        "stat_definition",
        ("id",),
        "CASCADE",
    ),
    (
        "tenant_admin_campaign_opt_out",
        "tenant_admin_campaign_opt_out_campaign_id_fkey",
        ("campaign_id",),
        "campaign",
        ("id",),
        "CASCADE",
    ),
]


def _unique_name(table: str, columns: tuple[str, ...]) -> str:
    return f"{table}_{'_'.join(columns)}_tenant_id_key"


def _on_delete(action: str | None) -> str:
    return f" ON DELETE {action}" if action else ""


def upgrade() -> None:
    for table, columns in _REFERENCED:
        cols = ", ".join(f'"{c}"' for c in (*columns, "tenant_id"))
        op.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT {_unique_name(table, columns)} UNIQUE ({cols})'
        )
    for table, name, columns, target, target_columns, action in _KEYS:
        cols = ", ".join(f'"{c}"' for c in (*columns, "tenant_id"))
        target_cols = ", ".join(f'"{c}"' for c in (*target_columns, "tenant_id"))
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT {name}')
        op.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT {name} FOREIGN KEY ({cols}) '
            f'REFERENCES "{target}" ({target_cols}){_on_delete(action)}'
        )


def downgrade() -> None:
    for table, name, columns, target, target_columns, action in _KEYS:
        cols = ", ".join(f'"{c}"' for c in columns)
        target_cols = ", ".join(f'"{c}"' for c in target_columns)
        single_action = "SET NULL" if action and action.startswith("SET NULL") else action
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT {name}')
        op.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT {name} FOREIGN KEY ({cols}) '
            f'REFERENCES "{target}" ({target_cols}){_on_delete(single_action)}'
        )
    for table, columns in reversed(_REFERENCED):
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT {_unique_name(table, columns)}')
