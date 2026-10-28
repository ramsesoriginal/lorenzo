"""Atomic manuscript move receipts (ADR 0344)."""

from alembic import op

revision = "c03440000001"
down_revision = "c03430000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_move (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      entry_id uuid NOT NULL,
      actor_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      request_hash text NOT NULL, acknowledgement jsonb NOT NULL, checkpoint jsonb NOT NULL,
      CONSTRAINT manuscript_move_entry_fkey FOREIGN KEY(entry_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_manuscript_move_tenant_id ON manuscript_move(tenant_id)")
    op.execute("CREATE INDEX ix_manuscript_move_entry_id ON manuscript_move(entry_id)")
    op.execute("ALTER TABLE manuscript_move ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_move FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON manuscript_move
      USING(tenant_id=current_setting('app.tenant_id')::uuid)""")


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_move")
