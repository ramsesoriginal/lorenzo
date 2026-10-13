"""stat definitions: a unit, a sign, adjustable in play, pinned; an order for definitions and groups

ADR 0278. How a stat is shown, and the order stats and groups come in. `position` is not dense and
not unique: a row inserted without one goes after its siblings (a trigger, as information.order
and entity_prototype.position do), and existing rows are numbered by name so that nothing moves.

Revision ID: d1f4b7a92c36
Revises: c8e2a5d19f47
Create Date: 2026-10-12 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1f4b7a92c36"
down_revision: str | None = "c8e2a5d19f47"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_DEFINITION_FUNCTION = """
CREATE FUNCTION stat_definition_default_position() RETURNS trigger AS $$
BEGIN
    IF NEW.position IS NULL THEN
        SELECT COALESCE(MAX(position) + 1, 0) INTO NEW.position
        FROM stat_definition
        WHERE stat_group_id = NEW.stat_group_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_GROUP_FUNCTION = """
CREATE FUNCTION stat_group_default_position() RETURNS trigger AS $$
BEGIN
    IF NEW.position IS NULL THEN
        SELECT COALESCE(MAX(position) + 1, 0) INTO NEW.position
        FROM stat_group
        WHERE tenant_id = NEW.tenant_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.add_column("stat_definition", sa.Column("unit", sa.Text(), nullable=True))
    for column in ("adjustable_in_play", "pin", "signed"):
        op.add_column(
            "stat_definition",
            sa.Column(column, sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    op.add_column("stat_definition", sa.Column("position", sa.Integer(), nullable=True))
    op.add_column("stat_group", sa.Column("position", sa.Integer(), nullable=True))

    # What is there keeps the order the clients showed it in: by name.
    op.execute(
        """
        UPDATE stat_definition sd SET position = ranked.position
        FROM (
            SELECT id,
                (ROW_NUMBER() OVER (PARTITION BY stat_group_id ORDER BY name, id) - 1)::integer
                    AS position
            FROM stat_definition
        ) ranked
        WHERE sd.id = ranked.id
        """
    )
    op.execute(
        """
        UPDATE stat_group sg SET position = ranked.position
        FROM (
            SELECT id,
                (ROW_NUMBER() OVER (PARTITION BY tenant_id ORDER BY name, id) - 1)::integer
                    AS position
            FROM stat_group
        ) ranked
        WHERE sg.id = ranked.id
        """
    )
    # The export revision (ADR 0262) is bumped by deferred triggers on these tables, and the
    # UPDATEs above queue their events: a table with pending events cannot be altered.
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.alter_column("stat_definition", "position", nullable=False)
    op.alter_column("stat_group", "position", nullable=False)
    op.execute(_DEFINITION_FUNCTION)
    op.execute(
        "CREATE TRIGGER stat_definition_default_position_trigger BEFORE INSERT ON stat_definition "
        "FOR EACH ROW EXECUTE FUNCTION stat_definition_default_position()"
    )
    op.execute(_GROUP_FUNCTION)
    op.execute(
        "CREATE TRIGGER stat_group_default_position_trigger BEFORE INSERT ON stat_group "
        "FOR EACH ROW EXECUTE FUNCTION stat_group_default_position()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER stat_group_default_position_trigger ON stat_group")
    op.execute("DROP FUNCTION stat_group_default_position()")
    op.execute("DROP TRIGGER stat_definition_default_position_trigger ON stat_definition")
    op.execute("DROP FUNCTION stat_definition_default_position()")
    op.drop_column("stat_group", "position")
    for column in ("position", "signed", "pin", "adjustable_in_play", "unit"):
        op.drop_column("stat_definition", column)
