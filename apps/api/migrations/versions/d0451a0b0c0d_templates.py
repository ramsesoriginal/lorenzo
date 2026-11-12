"""templates: a read-side view of an entry as data (ADR 0451)

`template` (a name, an optional game system, an optional kind and ancestor entry it is for),
`template_slot` (an ordered block: stats, information, held or tags), `template_slot_stat` (the
stats a slot lists, in order, with a label each) and `template_slot_exclusion` (the stats a group
slot leaves out). Every key is composite with tenant_id (ADR 0117), every table is repository
content (ADR 0118: tenant_isolation, repository_read) with FORCE ROW LEVEL SECURITY. A template
goes with its ancestor entry and a slot with its template; a stat group, a stat or a system a
template uses is not deleted (the API refuses).

Revision ID: d0451a0b0c0d
Revises: d0449a0b0c0d
Create Date: 2026-11-12 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0451a0b0c0d"
down_revision: str | None = "d0449a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"
_TABLES = ("template", "template_slot", "template_slot_stat", "template_slot_exclusion")


def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.UUID(), nullable=nullable)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _fk(
    name: str, table: str, columns: str, target: str, target_columns: str, ondelete: str = ""
) -> None:
    suffix = f" ON DELETE {ondelete}" if ondelete else ""
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({columns}) "
        f"REFERENCES {target} ({target_columns}){suffix}"
    )


def upgrade() -> None:
    op.create_table(
        "template",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        _uuid("tenant_id"),
        sa.Column("name", sa.Text(), nullable=False),
        _uuid("system_id", nullable=True),
        sa.Column("required_kind", sa.Text(), nullable=True),
        _uuid("required_ancestor_entry_id", nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="template_id_tenant_id_key"),
        sa.UniqueConstraint("tenant_id", "name", name="template_tenant_id_name_key"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    _fk("template_system_id_fkey", "template", "system_id, tenant_id", "system", "id, tenant_id")
    _fk(
        "template_required_ancestor_entry_id_fkey",
        "template",
        "required_ancestor_entry_id, tenant_id",
        "entity",
        "id, tenant_id",
        "CASCADE",
    )
    op.create_index("ix_template_tenant_id", "template", ["tenant_id"])
    op.create_index("ix_template_system_id", "template", ["system_id"])
    op.create_index(
        "ix_template_required_ancestor_entry_id", "template", ["required_ancestor_entry_id"]
    )

    op.create_table(
        "template_slot",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        _uuid("tenant_id"),
        _uuid("template_id"),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        _uuid("stat_group_id", nullable=True),
        sa.Column("information_type", sa.Text(), nullable=True),
        sa.Column("held_order", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="template_slot_id_tenant_id_key"),
        sa.UniqueConstraint(
            "template_id", "position", name="template_slot_template_id_position_key"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "kind IN ('stats', 'information', 'held', 'tags')", name="template_slot_kind"
        ),
        sa.CheckConstraint(
            "held_order IS NULL OR held_order IN ('name', 'prototype')",
            name="template_slot_held_order",
        ),
        sa.CheckConstraint(
            "(kind = 'information') = (information_type IS NOT NULL)",
            name="template_slot_information_type",
        ),
        sa.CheckConstraint(
            "(kind = 'held') = (held_order IS NOT NULL)", name="template_slot_held_order_of_held"
        ),
        sa.CheckConstraint(
            "kind <> 'information' OR stat_group_id IS NULL",
            name="template_slot_information_has_no_group",
        ),
    )
    _fk(
        "template_slot_template_id_fkey",
        "template_slot",
        "template_id, tenant_id",
        "template",
        "id, tenant_id",
        "CASCADE",
    )
    _fk(
        "template_slot_stat_group_id_fkey",
        "template_slot",
        "stat_group_id, tenant_id",
        "stat_group",
        "id, tenant_id",
    )
    op.create_index("ix_template_slot_tenant_id", "template_slot", ["tenant_id"])
    op.create_index("ix_template_slot_template_id", "template_slot", ["template_id"])
    op.create_index("ix_template_slot_stat_group_id", "template_slot", ["stat_group_id"])

    op.create_table(
        "template_slot_stat",
        _uuid("slot_id"),
        sa.Column("position", sa.Integer(), nullable=False),
        _uuid("tenant_id"),
        _uuid("stat_definition_id"),
        sa.Column("label", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("slot_id", "position"),
        sa.UniqueConstraint(
            "slot_id",
            "stat_definition_id",
            name="template_slot_stat_slot_id_stat_definition_id_key",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    _fk(
        "template_slot_stat_slot_id_fkey",
        "template_slot_stat",
        "slot_id, tenant_id",
        "template_slot",
        "id, tenant_id",
        "CASCADE",
    )
    _fk(
        "template_slot_stat_stat_definition_id_fkey",
        "template_slot_stat",
        "stat_definition_id, tenant_id",
        "stat_definition",
        "id, tenant_id",
    )
    op.create_index("ix_template_slot_stat_tenant_id", "template_slot_stat", ["tenant_id"])
    op.create_index(
        "ix_template_slot_stat_stat_definition_id", "template_slot_stat", ["stat_definition_id"]
    )

    op.create_table(
        "template_slot_exclusion",
        _uuid("slot_id"),
        _uuid("stat_definition_id"),
        _uuid("tenant_id"),
        sa.PrimaryKeyConstraint("slot_id", "stat_definition_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    _fk(
        "template_slot_exclusion_slot_id_fkey",
        "template_slot_exclusion",
        "slot_id, tenant_id",
        "template_slot",
        "id, tenant_id",
        "CASCADE",
    )
    _fk(
        "template_slot_exclusion_stat_definition_id_fkey",
        "template_slot_exclusion",
        "stat_definition_id, tenant_id",
        "stat_definition",
        "id, tenant_id",
    )
    op.create_index(
        "ix_template_slot_exclusion_tenant_id", "template_slot_exclusion", ["tenant_id"]
    )

    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = {_TENANT})")
        op.execute(
            f"CREATE POLICY repository_read ON {table} FOR SELECT "
            "USING (tenant_id = (SELECT repository_read_tenant_id()))"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_table(table)
