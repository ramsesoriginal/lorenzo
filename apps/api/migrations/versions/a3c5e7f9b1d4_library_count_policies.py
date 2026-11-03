"""the repository's side may count the libraries that still hold a row (ADR 0386)

`repository_owner_count`, a SELECT policy on the three copy-link tables: a link is visible to the
tenant it was copied from, and only while `app.library_count` is `on`, which only the count sets
(the setting-gated pattern of the release fan-out, ADR 0092, on ADR 0204's owner-side read). A
partial index on each keeps the count an index scan. Writes stay under tenant_isolation.

Revision ID: a3c5e7f9b1d4
Revises: e1b6d4a9c370
Create Date: 2026-11-03 21:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3c5e7f9b1d4"
down_revision: str | None = "e1b6d4a9c370"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Each copy-link table and the column that holds the copy's own id.
_TABLES = {
    "repository_copy_link_entity": "entity_id",
    "repository_copy_link_stat_group": "stat_group_id",
    "repository_copy_link_stat_definition": "stat_definition_id",
}
_USING = (
    "source_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid "
    "AND current_setting('app.library_count', true) = 'on'"
)


def upgrade() -> None:
    for table, local in _TABLES.items():
        op.execute(f"CREATE POLICY repository_owner_count ON {table} FOR SELECT USING ({_USING})")
        op.execute(
            f"CREATE INDEX ix_{table}_source ON {table} (source_tenant_id, source_id) "
            f"WHERE {local} IS NOT NULL"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP INDEX ix_{table}_source")
        op.execute(f"DROP POLICY repository_owner_count ON {table}")
