"""Safe paragraph split receipts (ADR 0346)."""

from alembic import op

revision = "c03460000001"
down_revision = "c03450000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_split (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      entry_id uuid NOT NULL, first_payload_id uuid NOT NULL, second_payload_id uuid NOT NULL,
      actor_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now(), request_hash text NOT NULL,
      CONSTRAINT manuscript_split_entry_fkey FOREIGN KEY(entry_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_split_first_fkey FOREIGN KEY(first_payload_id,tenant_id)
        REFERENCES payload(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_split_second_fkey FOREIGN KEY(second_payload_id,tenant_id)
        REFERENCES payload(id,tenant_id) ON DELETE CASCADE)""")
    for column in ("tenant_id", "entry_id", "first_payload_id", "second_payload_id"):
        op.execute(f"CREATE INDEX ix_manuscript_split_{column} ON manuscript_split({column})")
    op.execute("ALTER TABLE manuscript_split ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_split FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON manuscript_split
      USING(tenant_id=current_setting('app.tenant_id')::uuid)""")


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_split")
