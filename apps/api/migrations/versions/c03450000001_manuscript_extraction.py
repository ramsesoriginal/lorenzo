"""Atomic Chapter extraction receipts (ADR 0345)."""

from alembic import op

revision = "c03450000001"
down_revision = "c03440000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_extraction (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      source_id uuid NOT NULL, chapter_id uuid NOT NULL,
      actor_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      request_hash text NOT NULL, checkpoint jsonb NOT NULL,
      CONSTRAINT manuscript_extraction_source_fkey FOREIGN KEY(source_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_extraction_chapter_fkey FOREIGN KEY(chapter_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    for column in ("tenant_id", "source_id", "chapter_id"):
        op.execute(
            f"CREATE INDEX ix_manuscript_extraction_{column} ON manuscript_extraction({column})"
        )
    op.execute("ALTER TABLE manuscript_extraction ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_extraction FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON manuscript_extraction
      USING(tenant_id=current_setting('app.tenant_id')::uuid)""")


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_extraction")
