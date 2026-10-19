"""Explicit calendar periods and minimal Event date associations (ADR 0309)."""

from collections.abc import Sequence

from alembic import op

revision: str = "c03090000001"
down_revision: str | None = "c03080000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE story_event ( entity_id uuid PRIMARY KEY, tenant_id uuid NOT NULL
        REFERENCES tenant(id) ON DELETE CASCADE, CONSTRAINT
        story_event_entity_tenant_key UNIQUE(entity_id,tenant_id), CONSTRAINT
        story_event_entity_fkey FOREIGN KEY(entity_id,tenant_id) REFERENCES
        entity(id,tenant_id) ON DELETE CASCADE)
    """)
    op.execute("""
        CREATE TABLE calendar_period ( entity_id uuid PRIMARY KEY, tenant_id uuid NOT
        NULL REFERENCES tenant(id) ON DELETE CASCADE, calendar_entity_id uuid NOT NULL,
        year integer NOT NULL, segment text, day integer, parent_entity_id uuid,
        CONSTRAINT calendar_period_entity_tenant_key UNIQUE(entity_id,tenant_id),
        CONSTRAINT calendar_period_calendar_tenant_key
        UNIQUE(entity_id,calendar_entity_id,tenant_id), CONSTRAINT
        calendar_period_coordinate_key UNIQUE NULLS NOT
        DISTINCT(calendar_entity_id,year,segment,day), CONSTRAINT
        calendar_period_entity_fkey FOREIGN KEY(entity_id,tenant_id) REFERENCES
        entity(id,tenant_id) ON DELETE CASCADE, CONSTRAINT calendar_period_calendar_fkey
        FOREIGN KEY(calendar_entity_id,tenant_id) REFERENCES
        calendar(entity_id,tenant_id) ON DELETE NO ACTION, CONSTRAINT
        calendar_period_parent_fkey FOREIGN
        KEY(parent_entity_id,calendar_entity_id,tenant_id) REFERENCES
        calendar_period(entity_id,calendar_entity_id,tenant_id) ON DELETE NO ACTION,
        CONSTRAINT calendar_period_year_range CHECK(year BETWEEN -1000000 AND 1000000),
        CONSTRAINT calendar_period_shape CHECK((segment IS NULL AND day IS NULL AND
        parent_entity_id IS NULL) OR (segment IS NOT NULL AND parent_entity_id IS NOT
        NULL AND (day IS NULL OR day BETWEEN 1 AND 1000))))
    """)
    op.execute("""
        CREATE TABLE entry_calendar_period ( entity_id uuid NOT NULL, period_entity_id
        uuid NOT NULL, tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
        PRIMARY KEY(entity_id,period_entity_id), CONSTRAINT
        entry_calendar_period_entry_fkey FOREIGN KEY(entity_id,tenant_id) REFERENCES
        entity(id,tenant_id) ON DELETE CASCADE, CONSTRAINT
        entry_calendar_period_period_fkey FOREIGN KEY(period_entity_id,tenant_id)
        REFERENCES calendar_period(entity_id,tenant_id) ON DELETE NO ACTION)
    """)
    op.execute("""
        CREATE INDEX ix_calendar_period_calendar_entity_id ON
        calendar_period(calendar_entity_id)
    """)
    op.execute("""
        CREATE INDEX ix_entry_calendar_period_period_entity_id ON
        entry_calendar_period(period_entity_id)
    """)
    for table in ("story_event", "calendar_period", "entry_calendar_period"):
        op.execute(f"CREATE INDEX ix_{table}_tenant_id ON {table}(tenant_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
        )
        op.execute(
            f"CREATE POLICY repository_read ON {table} FOR SELECT "
            "USING (tenant_id = (SELECT repository_read_tenant_id()))"
        )


def downgrade() -> None:
    for table in ("entry_calendar_period", "calendar_period", "story_event"):
        op.execute(f"DROP TABLE {table}")
