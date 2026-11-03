"""Scene extraction retry receipts (ADR 0378)."""

from alembic import op

revision = "c03780000001"
down_revision = "d0348c036901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_scene_extraction (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      source_id uuid NOT NULL, scene_id uuid NOT NULL, telling_id uuid NOT NULL,
      actor_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      request_hash text NOT NULL, checkpoint jsonb NOT NULL,
      CONSTRAINT manuscript_scene_extraction_source_fkey FOREIGN KEY(source_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_scene_extraction_scene_fkey FOREIGN KEY(scene_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_scene_extraction_telling_fkey FOREIGN KEY(telling_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    for column in ("tenant_id", "source_id", "scene_id", "telling_id"):
        op.execute(
            f"CREATE INDEX ix_manuscript_scene_extraction_{column} "
            f"ON manuscript_scene_extraction({column})"
        )
    op.execute("ALTER TABLE manuscript_scene_extraction ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_scene_extraction FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON manuscript_scene_extraction
      USING(tenant_id=current_setting('app.tenant_id')::uuid)""")


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_scene_extraction")
