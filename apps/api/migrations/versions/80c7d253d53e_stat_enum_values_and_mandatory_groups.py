"""stat_group.mandatory, enum stat value type, stat_definition_enum_value

Revision ID: 80c7d253d53e
Revises: b28ed28ca209
Create Date: 2026-09-24 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "80c7d253d53e"
down_revision: str | None = "b28ed28ca209"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Display-only (ADR 0103): nothing ever checks a mandatory group is
    # filled in.
    op.add_column(
        "stat_group",
        sa.Column("mandatory", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # Stored in entity_stat.value_text, so entity_stat's "exactly one value
    # column" check and v_effective_stat need no change (ADR 0103).
    op.execute("ALTER TYPE stat_value_type ADD VALUE IF NOT EXISTS 'enum'")

    op.create_table(
        "stat_definition_enum_value",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("stat_definition_id", sa.UUID(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        # A display hint, deliberately not unique.
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stat_definition_id"], ["stat_definition.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "stat_definition_id", "value", name="stat_definition_enum_value_unique"
        ),
    )
    op.create_index(
        "ix_stat_definition_enum_value_tenant_id", "stat_definition_enum_value", ["tenant_id"]
    )
    op.create_index(
        "ix_stat_definition_enum_value_stat_definition_id",
        "stat_definition_enum_value",
        ["stat_definition_id"],
    )
    op.execute("ALTER TABLE stat_definition_enum_value ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stat_definition_enum_value FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON stat_definition_enum_value "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.drop_table("stat_definition_enum_value")
    # Postgres can't drop one enum member, so the type is rebuilt without
    # it. Refuses (the cast fails) while any definition still uses `enum`
    # - a downgrade must not silently retype a tenant's stats.
    op.execute("ALTER TYPE stat_value_type RENAME TO stat_value_type_old")
    op.execute("CREATE TYPE stat_value_type AS ENUM ('int', 'text', 'float', 'bool')")
    op.execute(
        "ALTER TABLE stat_definition ALTER COLUMN value_type TYPE stat_value_type "
        "USING value_type::text::stat_value_type"
    )
    op.execute("DROP TYPE stat_value_type_old")
    op.drop_column("stat_group", "mandatory")
