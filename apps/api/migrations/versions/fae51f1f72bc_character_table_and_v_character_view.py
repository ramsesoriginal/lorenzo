"""character table and v_character view

Revision ID: fae51f1f72bc
Revises: a22dc991a926
Create Date: 2026-09-11 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fae51f1f72bc"
down_revision: str | None = "a22dc991a926"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


# security_invoker: Postgres views run with the view owner's privileges by
# default, not the querying role's - without this, RLS on the underlying
# tables would be silently bypassed (ADR 0002/0012/0019).
_CREATE_V_CHARACTER = """
    CREATE VIEW v_character WITH (security_invoker = true) AS
    SELECT
        c.entity_id AS entity_id,
        c.tenant_id AS tenant_id,
        c.owner_player_id AS owner_player_id,
        description_info.id AS description_id,
        description_info.title AS title,
        containment.parent_entity_id AS container_entity_id
    FROM character c
    JOIN being b ON b.entity_id = c.entity_id
    JOIN entity e ON e.id = c.entity_id
    LEFT JOIN information description_info
        ON description_info.entity_id = e.id AND description_info.type = 'description'
    LEFT JOIN containment ON containment.child_entity_id = e.id
    """


def upgrade() -> None:
    # entity_id is PK *and* FK to being.entity_id, not entity.id directly -
    # the first three-level class-table-inheritance chain in this schema
    # (entity -> being -> character), ADR 0031/RFC 0004.
    op.create_table(
        "character",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("owner_player_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.ForeignKeyConstraint(["entity_id"], ["being.entity_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_player_id"], ["player.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_character_tenant_id"), "character", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_character_owner_player_id"), "character", ["owner_player_id"], unique=False
    )
    op.create_index(op.f("ix_character_created_by"), "character", ["created_by"], unique=False)
    op.create_index(op.f("ix_character_updated_by"), "character", ["updated_by"], unique=False)
    _enable_rls("character")

    # being.owner_player_id moves to character.owner_player_id - confirmed
    # zero being rows exist yet (pre-release), so no backfill is needed,
    # unlike campaign's entity_id in ADR 0030.
    op.drop_constraint("being_owner_player_id_fkey", "being", type_="foreignkey")
    op.drop_index(op.f("ix_being_owner_player_id"), table_name="being")
    op.drop_column("being", "owner_player_id")

    # character_player/group_member retarget from being.entity_id to
    # character.entity_id - a being now has to be "promoted" to a character
    # row before it can be rostered or group-linked (ADR 0031/RFC 0004).
    # Confirmed zero rows in either table, so no data to reconcile.
    op.drop_constraint(
        "character_player_character_entity_id_fkey", "character_player", type_="foreignkey"
    )
    op.create_foreign_key(
        "character_player_character_entity_id_fkey",
        "character_player",
        "character",
        ["character_entity_id"],
        ["entity_id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("group_member_character_entity_id_fkey", "group_member", type_="foreignkey")
    op.create_foreign_key(
        "group_member_character_entity_id_fkey",
        "group_member",
        "character",
        ["character_entity_id"],
        ["entity_id"],
        ondelete="CASCADE",
    )

    op.execute(_CREATE_V_CHARACTER)


def downgrade() -> None:
    # Retargeting character_player/group_member back to being.entity_id is
    # only safe if every character_entity_id currently in either table is
    # also a real being.entity_id, which it always transitively is *for
    # rows created under this migration's own schema* (character.entity_id
    # is itself an FK to being.entity_id). It is NOT safe to downgrade,
    # then upgrade again, past real character_player/group_member rows
    # still present: the character table gets dropped (its data is gone
    # for good) but character_player/group_member's own rows survive the
    # round trip untouched, so re-upgrading tries to point their FK back
    # at a freshly emptied character table their surviving rows no longer
    # have matching entries in - confirmed empirically, not just reasoned
    # through, the same way ADR 0030's own downgrade note names its
    # analogous "backfilled Entity rows aren't cleaned up here" gap. Not
    # a concern for a real one-way rollback (which wouldn't be immediately
    # followed by a re-upgrade), only for a downgrade+upgrade round-trip
    # check against a database that already has real rows - run that kind
    # of check against an empty schema, or expect to clean up by hand.
    op.execute("DROP VIEW v_character")

    op.drop_constraint("group_member_character_entity_id_fkey", "group_member", type_="foreignkey")
    op.create_foreign_key(
        "group_member_character_entity_id_fkey",
        "group_member",
        "being",
        ["character_entity_id"],
        ["entity_id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "character_player_character_entity_id_fkey", "character_player", type_="foreignkey"
    )
    op.create_foreign_key(
        "character_player_character_entity_id_fkey",
        "character_player",
        "being",
        ["character_entity_id"],
        ["entity_id"],
        ondelete="CASCADE",
    )

    op.add_column("being", sa.Column("owner_player_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_being_owner_player_id"), "being", ["owner_player_id"], unique=False)
    op.create_foreign_key(
        "being_owner_player_id_fkey",
        "being",
        "player",
        ["owner_player_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_index(op.f("ix_character_updated_by"), table_name="character")
    op.drop_index(op.f("ix_character_created_by"), table_name="character")
    op.drop_index(op.f("ix_character_owner_player_id"), table_name="character")
    op.drop_index(op.f("ix_character_tenant_id"), table_name="character")
    op.drop_table("character")
