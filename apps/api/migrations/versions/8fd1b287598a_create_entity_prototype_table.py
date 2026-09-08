"""create entity_prototype table

Revision ID: 8fd1b287598a
Revises: ae4e64d66f9f
Create Date: 2026-09-08 16:39:16.199970

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8fd1b287598a"
down_revision: str | None = "ae4e64d66f9f"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Recursive CTE: starting from the new row's prototype_id, walk that
# entity's own prototype chain (its prototypes, their prototypes, ...). If
# the new row's entity_id already appears in that chain, prototype_id
# already transitively inherits from entity_id, and adding this edge would
# close a loop. Direct self-loops (entity_id = prototype_id) are instead
# rejected by the CHECK constraint - see ADR 0015 for why both are needed.
#
# Two separate op.execute() calls, not one: asyncpg prepares every statement
# it sends, and Postgres's extended query protocol rejects multiple commands
# in a single prepared statement ("cannot insert multiple commands into a
# prepared statement") - confirmed the hard way running this migration.
_CREATE_CYCLE_FUNCTION = """
CREATE FUNCTION entity_prototype_reject_cycles() RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        WITH RECURSIVE ancestors(ancestor_id) AS (
            SELECT prototype_id FROM entity_prototype WHERE entity_id = NEW.prototype_id
            UNION
            SELECT ep.prototype_id
            FROM entity_prototype ep
            JOIN ancestors a ON ep.entity_id = a.ancestor_id
        )
        SELECT 1 FROM ancestors WHERE ancestor_id = NEW.entity_id
    ) THEN
        RAISE EXCEPTION
            'entity_prototype: cycle detected (% already transitively inherits from %)',
            NEW.prototype_id, NEW.entity_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_CREATE_CYCLE_TRIGGER = """
CREATE TRIGGER entity_prototype_reject_cycles_trigger
    BEFORE INSERT ON entity_prototype
    FOR EACH ROW EXECUTE FUNCTION entity_prototype_reject_cycles();
"""


def upgrade() -> None:
    op.create_table(
        "entity_prototype",
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("prototype_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("entity_id <> prototype_id", name="entity_prototype_no_self_loop"),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"]),
        sa.ForeignKeyConstraint(["prototype_id"], ["entity.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("entity_id", "prototype_id"),
    )
    op.create_index(
        op.f("ix_entity_prototype_tenant_id"), "entity_prototype", ["tenant_id"], unique=False
    )

    # See ADR 0012 for why both ENABLE and FORCE are needed, and ADR 0002 for
    # the currently-unenforced-in-practice caveat (the app's own DB role is a
    # superuser, which bypasses RLS unconditionally, independent of this
    # policy being correct).
    op.execute("ALTER TABLE entity_prototype ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE entity_prototype FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON entity_prototype "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )

    op.execute(_CREATE_CYCLE_FUNCTION)
    op.execute(_CREATE_CYCLE_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER entity_prototype_reject_cycles_trigger ON entity_prototype")
    op.execute("DROP FUNCTION entity_prototype_reject_cycles()")
    op.drop_index(op.f("ix_entity_prototype_tenant_id"), table_name="entity_prototype")
    op.drop_table("entity_prototype")
