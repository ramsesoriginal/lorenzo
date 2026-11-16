"""Relationships: an optional start and end Event (ADR 0405).

Each is a same-tenant composite key into story_event that clears only its own column when the Event
is deleted (PostgreSQL 15+); the Event's delete leaves a staff note on what it bounded.
"""

from alembic import op

revision = "c04050000001"
down_revision = "c04020000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("starts_at", "ends_at"):
        op.execute(f"ALTER TABLE relationship ADD COLUMN {column} uuid NULL")
        op.execute(
            f"ALTER TABLE relationship ADD CONSTRAINT relationship_{column}_fkey "
            f"FOREIGN KEY ({column}, tenant_id) REFERENCES story_event(entity_id, tenant_id) "
            f"ON DELETE SET NULL ({column})"
        )
        op.execute(f"CREATE INDEX ix_relationship_{column} ON relationship(tenant_id, {column})")
    op.execute(
        "ALTER TABLE relationship ADD CONSTRAINT relationship_limits_differ "
        "CHECK (starts_at IS NULL OR ends_at IS NULL OR starts_at <> ends_at)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE relationship DROP CONSTRAINT relationship_limits_differ")
    for column in ("starts_at", "ends_at"):
        op.execute(f"ALTER TABLE relationship DROP COLUMN {column}")
