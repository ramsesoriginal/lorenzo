"""editable information: information_type, singleton index, order, created_by

Revision ID: b28ed28ca209
Revises: 7d2e4b6a9c10
Create Date: 2026-09-24 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import make_url

from lorenzo_api.config import get_settings

revision: str = "b28ed28ca209"
down_revision: str | None = "7d2e4b6a9c10"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# ADR 0101: the partial index predicate can't read information_type, so this
# literal list and the catalog's is_singleton rows are two separately
# maintained facts. tests/test_information_type.py checks they agree.
_SINGLETON_TYPES = ("description", "main_picture")

# "order omitted -> append after the last sibling" (ADR 0101), in the
# database rather than the app, so every writer (the API, tests, seeds)
# gets the same rule. Concurrent appends to one parent are serialized by
# the API taking the parent entity's row lock first; this trigger alone
# doesn't prevent that race, the unique constraint just rejects it.
_APPEND_ORDER_FUNCTIONS = {
    "information": "entity_id",
    "payload": "information_id",
}


def _append_order_sql(table: str, parent_column: str) -> tuple[str, str]:
    """(function, trigger) - two statements, since asyncpg runs one per
    execute."""
    function = f"""
CREATE FUNCTION {table}_append_order() RETURNS trigger AS $$
BEGIN
    IF NEW."order" IS NULL THEN
        SELECT COALESCE(MAX("order") + 1, 0) INTO NEW."order"
        FROM {table}
        WHERE {parent_column} = NEW.{parent_column};
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""
    trigger = f"""
CREATE TRIGGER {table}_append_order_trigger
    BEFORE INSERT ON {table}
    FOR EACH ROW EXECUTE FUNCTION {table}_append_order()
"""
    return function, trigger


# The app role, the same way 8aced4b80842 derives it (ADR 0021).
_APP_ROLE = make_url(get_settings().database_url).username


def upgrade() -> None:
    # Global catalog, not tenant data: no tenant_id, no RLS. Default
    # privileges would hand the app role full CRUD on it, so writes are
    # revoked below - only migrations change this table.
    op.create_table(
        "information_type",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_singleton", sa.Boolean(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
        sa.CheckConstraint(
            "category IN ('technical', 'gm_authored')", name="information_type_category"
        ),
    )
    op.bulk_insert(
        sa.table(
            "information_type",
            sa.column("name", sa.Text()),
            sa.column("is_singleton", sa.Boolean()),
            sa.column("category", sa.Text()),
        ),
        [
            {"name": name, "is_singleton": True, "category": "technical"}
            for name in _SINGLETON_TYPES
        ],
    )
    if _APP_ROLE is not None:
        op.execute(f'REVOKE INSERT, UPDATE, DELETE ON information_type FROM "{_APP_ROLE}"')

    op.drop_constraint("information_entity_id_type_key", "information", type_="unique")
    singleton_list = ", ".join(f"'{name}'" for name in _SINGLETON_TYPES)
    op.execute(
        "CREATE UNIQUE INDEX information_singleton_type ON information (entity_id, type) "
        f"WHERE type IN ({singleton_list})"
    )

    # order: added nullable, backfilled 0, 1, 2, ... per parent by creation
    # time, then made NOT NULL and unique per parent.
    op.add_column("information", sa.Column("order", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE information i SET "order" = ranked.position
        FROM (
            SELECT id, row_number() OVER (
                PARTITION BY entity_id ORDER BY created_at, id
            ) - 1 AS position
            FROM information
        ) ranked
        WHERE ranked.id = i.id
    """)
    op.alter_column("information", "order", nullable=False)
    op.create_unique_constraint("information_entity_order", "information", ["entity_id", "order"])

    op.add_column("payload", sa.Column("order", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE payload p SET "order" = ranked.position
        FROM (
            SELECT id, row_number() OVER (
                PARTITION BY information_id ORDER BY created_at, id
            ) - 1 AS position
            FROM payload
        ) ranked
        WHERE ranked.id = p.id
    """)
    op.alter_column("payload", "order", nullable=False)
    op.create_unique_constraint("payload_information_order", "payload", ["information_id", "order"])
    for table, parent_column in _APPEND_ORDER_FUNCTIONS.items():
        for statement in _append_order_sql(table, parent_column):
            op.execute(statement)

    # ADR 0029 deferred attribution on information until its write path was
    # designed; ADR 0101's edit rule needs it. Existing rows stay NULL.
    op.add_column("information", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "information_created_by_fkey",
        "information",
        "app_user",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_information_created_by", "information", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_information_created_by", table_name="information")
    op.drop_constraint("information_created_by_fkey", "information", type_="foreignkey")
    op.drop_column("information", "created_by")
    for table in _APPEND_ORDER_FUNCTIONS:
        op.execute(f"DROP TRIGGER {table}_append_order_trigger ON {table}")
        op.execute(f"DROP FUNCTION {table}_append_order()")
    op.drop_constraint("payload_information_order", "payload", type_="unique")
    op.drop_column("payload", "order")
    op.drop_constraint("information_entity_order", "information", type_="unique")
    op.drop_column("information", "order")
    op.execute("DROP INDEX information_singleton_type")
    # Fails if an entity now holds two rows of one type - deliberately: the
    # old blanket constraint can't be restored without deciding which to
    # delete, and a downgrade must not silently drop data.
    op.create_unique_constraint(
        "information_entity_id_type_key", "information", ["entity_id", "type"]
    )
    op.drop_table("information_type")
