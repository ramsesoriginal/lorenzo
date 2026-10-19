"""Recurring observance entries (ADR 0310)."""

from collections.abc import Sequence

from alembic import op

revision: str = "c03100000001"
down_revision: str | None = "c03090000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE calendar_observance (
            entity_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
            calendar_entity_id uuid NOT NULL,
            rule jsonb NOT NULL,
            CONSTRAINT calendar_observance_entity_tenant_key UNIQUE(entity_id,tenant_id),
            CONSTRAINT calendar_observance_entity_fkey FOREIGN KEY(entity_id,tenant_id)
                REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
            CONSTRAINT calendar_observance_calendar_fkey FOREIGN KEY(calendar_entity_id,tenant_id)
                REFERENCES calendar(entity_id,tenant_id) ON DELETE NO ACTION
        )
    """)
    op.execute("CREATE INDEX ix_calendar_observance_tenant_id ON calendar_observance(tenant_id)")
    op.execute("""CREATE INDEX ix_calendar_observance_calendar_entity_id
        ON calendar_observance(calendar_entity_id)""")
    op.execute("ALTER TABLE calendar_observance ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE calendar_observance FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON calendar_observance
        USING (tenant_id = current_setting('app.tenant_id')::uuid)""")
    op.execute("""CREATE POLICY repository_read ON calendar_observance FOR SELECT
        USING (tenant_id = (SELECT repository_read_tenant_id()))""")


def downgrade() -> None:
    op.execute("DROP TABLE calendar_observance")
