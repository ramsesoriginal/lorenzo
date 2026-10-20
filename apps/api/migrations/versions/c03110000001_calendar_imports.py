"""Atomic calendar import provenance and retry receipts (ADR 0311)."""

from collections.abc import Sequence

from alembic import op

revision: str = "c03110000001"
down_revision: str | None = "c03100000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE calendar_import (
        tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
        source_key text NOT NULL, calendar_entity_id uuid NOT NULL,
        document jsonb NOT NULL, bindings jsonb NOT NULL, receipt jsonb NOT NULL,
        last_token text, last_request_hash text,
        updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(tenant_id,source_key),
        CONSTRAINT calendar_import_calendar_fkey FOREIGN KEY(calendar_entity_id,tenant_id)
            REFERENCES calendar(entity_id,tenant_id) ON DELETE CASCADE
    )""")
    op.execute("CREATE INDEX ix_calendar_import_tenant_id ON calendar_import(tenant_id)")
    op.execute("ALTER TABLE calendar_import ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE calendar_import FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON calendar_import
        USING (tenant_id = current_setting('app.tenant_id')::uuid)""")


def downgrade() -> None:
    op.execute("DROP TABLE calendar_import")
