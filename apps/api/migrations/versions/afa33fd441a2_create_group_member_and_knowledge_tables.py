"""create group_member and knowledge tables

Revision ID: afa33fd441a2
Revises: f1fe7e3cc925
Create Date: 2026-09-09 20:49:14.415374

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "afa33fd441a2"
down_revision: str | None = "f1fe7e3cc925"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT_SCOPED_TABLES = ("group_member", "knowledge")


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "group_member",
        sa.Column("group_entity_id", sa.UUID(), nullable=False),
        sa.Column("character_entity_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "group_entity_id <> character_entity_id", name="group_member_no_self_loop"
        ),
        sa.PrimaryKeyConstraint("group_entity_id", "character_entity_id"),
        sa.ForeignKeyConstraint(["group_entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["character_entity_id"], ["being.entity_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_group_member_tenant_id"), "group_member", ["tenant_id"], unique=False)

    op.create_table(
        "knowledge",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        # Nullable - exactly one of knower_entity_id/knower_player_id is set
        # per row (CHECK below). knower_entity_id covers both a single
        # character (a being) and a group (a bare entity with group_member
        # rows) - one column, two referents, per RFC 0001.
        sa.Column("knower_entity_id", sa.UUID(), nullable=True),
        sa.Column("knower_player_id", sa.UUID(), nullable=True),
        sa.Column("information_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "num_nonnulls(knower_entity_id, knower_player_id) = 1",
            name="knowledge_exactly_one_knower",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["knower_entity_id"], ["entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knower_player_id"], ["player.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["information_id"], ["information.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        # Every other join table gets duplicate-knower prevention for free
        # from its composite PK; knowledge needs a surrogate PK instead (a
        # composite PK can't contain these always-one-null columns), so
        # these two UNIQUEs restore that property explicitly. NULL is
        # distinct from NULL in a plain UNIQUE constraint, so neither
        # interferes with the other, and several different knowers can
        # still share one information_id.
        sa.UniqueConstraint(
            "knower_entity_id", "information_id", name="knowledge_unique_entity_knower_information"
        ),
        sa.UniqueConstraint(
            "knower_player_id", "information_id", name="knowledge_unique_player_knower_information"
        ),
    )
    op.create_index(op.f("ix_knowledge_tenant_id"), "knowledge", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_knowledge_knower_entity_id"), "knowledge", ["knower_entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_knowledge_knower_player_id"), "knowledge", ["knower_player_id"], unique=False
    )
    op.create_index(
        op.f("ix_knowledge_information_id"), "knowledge", ["information_id"], unique=False
    )

    # Completes RFC 0001's fourth knower case ("known to everyone") -
    # deferred by ADR 0017 specifically because the knowledge system it
    # depends on wasn't built yet.
    op.add_column(
        "information",
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    for table in _TENANT_SCOPED_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_column("information", "is_public")

    op.drop_index(op.f("ix_knowledge_information_id"), table_name="knowledge")
    op.drop_index(op.f("ix_knowledge_knower_player_id"), table_name="knowledge")
    op.drop_index(op.f("ix_knowledge_knower_entity_id"), table_name="knowledge")
    op.drop_index(op.f("ix_knowledge_tenant_id"), table_name="knowledge")
    op.drop_table("knowledge")

    op.drop_index(op.f("ix_group_member_tenant_id"), table_name="group_member")
    op.drop_table("group_member")
