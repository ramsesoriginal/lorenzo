"""entity_prototype.position: the order of an entry's parents, and the stat tie-break it gives

Revision ID: d7a3f1b9c2e4
Revises: c4e7a19b5d28
Create Date: 2026-10-11 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7a3f1b9c2e4"
down_revision: str | None = "c4e7a19b5d28"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Unchanged from 5fade6f98352 (ADR 0037, 0039).
_MAX_PROTOTYPE_DEPTH = 50

# A row inserted without a position goes last among its entry's parents. The column is NOT NULL
# and has no default, so the trigger (which runs before the constraint is checked) is what fills
# it: every existing writer that adds a parent keeps working and appends.
_CREATE_POSITION_FUNCTION = """
CREATE FUNCTION entity_prototype_default_position() RETURNS trigger AS $$
BEGIN
    IF NEW.position IS NULL THEN
        SELECT COALESCE(MAX(position) + 1, 0) INTO NEW.position
        FROM entity_prototype
        WHERE entity_id = NEW.entity_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_CREATE_POSITION_TRIGGER = """
CREATE TRIGGER entity_prototype_default_position_trigger
    BEFORE INSERT ON entity_prototype
    FOR EACH ROW EXECUTE FUNCTION entity_prototype_default_position();
"""

# ADR 0266: at equal distance and equal priority the earlier parent wins. `path` is the positions
# taken from the entry down to the ancestor, so two ancestors at the same distance compare by the
# first parent they were reached through, then by the next one, and so on. The entity id stays the
# last resort (one ancestor reached through two paths, or two positions that are equal).
_V_EFFECTIVE_STAT_SQL = f"""
    CREATE OR REPLACE VIEW v_effective_stat WITH (security_invoker = true) AS
    WITH RECURSIVE
        stat_ancestor(root_entity_id, ancestor_id, hops, path) AS (
            SELECT e.id, e.id, 0, ARRAY[]::integer[]
            FROM entity e
            UNION ALL
            SELECT sa.root_entity_id, ep.prototype_id, sa.hops + 1, sa.path || ep.position
            FROM stat_ancestor sa
            JOIN entity_prototype ep ON ep.entity_id = sa.ancestor_id
            WHERE sa.hops < {_MAX_PROTOTYPE_DEPTH}
        ),
        ancestor_priority AS (
            SELECT esg.entity_id, MAX(sg.priority) AS priority
            FROM entity_stat_group esg
            JOIN stat_group sg ON sg.id = esg.stat_group_id
            GROUP BY esg.entity_id
        ),
        candidate AS (
            SELECT es.entity_id AS holder_id, es.stat_definition_id,
                es.value_int, es.value_text, es.value_float, es.value_bool,
                false AS is_computed
            FROM entity_stat es
            UNION ALL
            SELECT cs.entity_id, cs.stat_definition_id,
                NULL::integer, NULL::text, NULL::double precision, NULL::boolean,
                true
            FROM computed_stat cs
        )
    SELECT DISTINCT ON (sa.root_entity_id, c.stat_definition_id)
        sa.root_entity_id AS entity_id,
        e.tenant_id AS tenant_id,
        c.stat_definition_id AS stat_definition_id,
        c.value_int AS value_int,
        c.value_text AS value_text,
        c.value_float AS value_float,
        c.value_bool AS value_bool,
        CASE WHEN c.is_computed THEN c.holder_id END AS computed_entity_id
    FROM stat_ancestor sa
    JOIN entity e ON e.id = sa.root_entity_id
    JOIN candidate c ON c.holder_id = sa.ancestor_id
    LEFT JOIN ancestor_priority ap ON ap.entity_id = sa.ancestor_id
    ORDER BY
        sa.root_entity_id,
        c.stat_definition_id,
        sa.hops ASC,
        c.is_computed ASC,
        COALESCE(ap.priority, 0) DESC,
        sa.path ASC,
        sa.ancestor_id
    """

# As 5fade6f98352 left it - for downgrade.
_PREVIOUS_V_EFFECTIVE_STAT_SQL = f"""
    CREATE OR REPLACE VIEW v_effective_stat WITH (security_invoker = true) AS
    WITH RECURSIVE
        stat_ancestor(root_entity_id, ancestor_id, hops) AS (
            SELECT e.id, e.id, 0
            FROM entity e
            UNION ALL
            SELECT sa.root_entity_id, ep.prototype_id, sa.hops + 1
            FROM stat_ancestor sa
            JOIN entity_prototype ep ON ep.entity_id = sa.ancestor_id
            WHERE sa.hops < {_MAX_PROTOTYPE_DEPTH}
        ),
        ancestor_priority AS (
            SELECT esg.entity_id, MAX(sg.priority) AS priority
            FROM entity_stat_group esg
            JOIN stat_group sg ON sg.id = esg.stat_group_id
            GROUP BY esg.entity_id
        ),
        candidate AS (
            SELECT es.entity_id AS holder_id, es.stat_definition_id,
                es.value_int, es.value_text, es.value_float, es.value_bool,
                false AS is_computed
            FROM entity_stat es
            UNION ALL
            SELECT cs.entity_id, cs.stat_definition_id,
                NULL::integer, NULL::text, NULL::double precision, NULL::boolean,
                true
            FROM computed_stat cs
        )
    SELECT DISTINCT ON (sa.root_entity_id, c.stat_definition_id)
        sa.root_entity_id AS entity_id,
        e.tenant_id AS tenant_id,
        c.stat_definition_id AS stat_definition_id,
        c.value_int AS value_int,
        c.value_text AS value_text,
        c.value_float AS value_float,
        c.value_bool AS value_bool,
        CASE WHEN c.is_computed THEN c.holder_id END AS computed_entity_id
    FROM stat_ancestor sa
    JOIN entity e ON e.id = sa.root_entity_id
    JOIN candidate c ON c.holder_id = sa.ancestor_id
    LEFT JOIN ancestor_priority ap ON ap.entity_id = sa.ancestor_id
    ORDER BY
        sa.root_entity_id,
        c.stat_definition_id,
        sa.hops ASC,
        c.is_computed ASC,
        COALESCE(ap.priority, 0) DESC,
        sa.ancestor_id
    """


def upgrade() -> None:
    op.add_column("entity_prototype", sa.Column("position", sa.Integer(), nullable=True))
    # What is there keeps the order it was read in (by id), so no stat resolves differently than
    # it did before this migration: the old last resort was the ancestor id.
    op.execute(
        """
        UPDATE entity_prototype ep SET position = ranked.position
        FROM (
            SELECT entity_id, prototype_id,
                (ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY prototype_id) - 1)::integer
                    AS position
            FROM entity_prototype
        ) ranked
        WHERE ep.entity_id = ranked.entity_id AND ep.prototype_id = ranked.prototype_id
        """
    )
    # The export revision (ADR 0262) is bumped by deferred triggers on this table, and the UPDATE
    # above queues their events: a table with pending events cannot be altered, so they run now.
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.alter_column("entity_prototype", "position", nullable=False)
    op.execute(_CREATE_POSITION_FUNCTION)
    op.execute(_CREATE_POSITION_TRIGGER)
    op.execute(_V_EFFECTIVE_STAT_SQL)


def downgrade() -> None:
    op.execute(_PREVIOUS_V_EFFECTIVE_STAT_SQL)
    op.execute("DROP TRIGGER entity_prototype_default_position_trigger ON entity_prototype")
    op.execute("DROP FUNCTION entity_prototype_default_position()")
    op.drop_column("entity_prototype", "position")
