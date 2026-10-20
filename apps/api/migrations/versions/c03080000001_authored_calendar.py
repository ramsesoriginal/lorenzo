"""Authored calendar definitions (ADR 0308)."""

from collections.abc import Sequence

from alembic import op

revision: str = "c03080000001"
down_revision: str | None = "a44f03050001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE calendar (
        entity_id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
        definition jsonb NOT NULL CHECK (definition->>'format' = 'lorenzo.calendar/1'),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT calendar_entity_id_tenant_id_key UNIQUE(entity_id,tenant_id),
        CONSTRAINT calendar_entity_id_fkey FOREIGN KEY(entity_id,tenant_id)
            REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_calendar_tenant_id ON calendar(tenant_id)")
    op.execute("ALTER TABLE calendar ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE calendar FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON calendar USING ("
        "tenant_id = current_setting('app.tenant_id')::uuid)"
    )
    op.execute(
        "CREATE POLICY repository_read ON calendar FOR SELECT USING ("
        "tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE calendar")
