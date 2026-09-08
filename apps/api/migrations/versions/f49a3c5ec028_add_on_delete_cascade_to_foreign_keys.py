"""add ON DELETE CASCADE to every foreign key

Revision ID: f49a3c5ec028
Revises: adf5b3b769e7
Create Date: 2026-09-08 17:44:50.642321

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f49a3c5ec028"
down_revision: str | None = "adf5b3b769e7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# (table, column, referenced_table) for every foreign key in the schema so
# far. Every one of these is genuine composition - see ADR 0018 - so this
# applies uniformly rather than picking constraints case by case. Alembic's
# autogenerate actually caught this diff correctly in this environment (drop
# + recreate each constraint), but its auto-generated downgrade uses `None`
# as a placeholder constraint name wherever the matching create used `None`
# - which errors if actually run - so this is hand-written with explicit,
# confirmed-real names (verified against pg_constraint) in both directions
# instead of trusting that output as-is.
_FOREIGN_KEYS = (
    ("entity", "tenant_id", "tenant"),
    ("stat_group", "tenant_id", "tenant"),
    ("stat_definition", "tenant_id", "tenant"),
    ("stat_definition", "stat_group_id", "stat_group"),
    ("entity_stat_group", "entity_id", "entity"),
    ("entity_stat_group", "stat_group_id", "stat_group"),
    ("entity_stat_group", "tenant_id", "tenant"),
    ("entity_stat", "entity_id", "entity"),
    ("entity_stat", "stat_definition_id", "stat_definition"),
    ("entity_stat", "tenant_id", "tenant"),
    ("entity_prototype", "entity_id", "entity"),
    ("entity_prototype", "prototype_id", "entity"),
    ("entity_prototype", "tenant_id", "tenant"),
    ("containment", "child_entity_id", "entity"),
    ("containment", "parent_entity_id", "entity"),
    ("containment", "tenant_id", "tenant"),
    ("information", "entity_id", "entity"),
    ("information", "tenant_id", "tenant"),
    ("payload", "information_id", "information"),
    ("payload", "tenant_id", "tenant"),
    ("payload_description", "payload_id", "payload"),
    ("payload_description", "tenant_id", "tenant"),
    ("payload_document", "payload_id", "payload"),
    ("payload_document", "tenant_id", "tenant"),
    ("payload_number", "payload_id", "payload"),
    ("payload_number", "tenant_id", "tenant"),
    ("payload_picture", "payload_id", "payload"),
    ("payload_picture", "tenant_id", "tenant"),
)


def upgrade() -> None:
    for table, column, ref_table in _FOREIGN_KEYS:
        constraint_name = f"{table}_{column}_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name, table, ref_table, [column], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    for table, column, ref_table in _FOREIGN_KEYS:
        constraint_name = f"{table}_{column}_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(constraint_name, table, ref_table, [column], ["id"])
