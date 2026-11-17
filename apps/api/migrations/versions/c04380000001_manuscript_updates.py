"""Atomic manuscript repository checkpoints (ADR 0438)."""

from alembic import op

revision = "c04380000001"
down_revision = "d0398c040601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_repository_update (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      entry_id uuid NOT NULL,
      actor_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      checkpoint jsonb NOT NULL,
      CONSTRAINT manuscript_repository_update_entry_fkey FOREIGN KEY(entry_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute(
        "CREATE INDEX ix_manuscript_repository_update_tenant_id ON "
        "manuscript_repository_update(tenant_id)"
    )
    op.execute(
        "CREATE INDEX ix_manuscript_repository_update_entry_id ON "
        "manuscript_repository_update(entry_id)"
    )
    op.execute("ALTER TABLE manuscript_repository_update ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_repository_update FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON manuscript_repository_update
      USING(tenant_id=current_setting('app.tenant_id')::uuid)""")


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_repository_update")
