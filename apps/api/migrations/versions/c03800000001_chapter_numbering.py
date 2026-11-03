"""Chapter numbering settings (ADR 0380)."""

from alembic import op

revision = "c03800000001"
down_revision = "c03790000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_numbering (
      entity_id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      settings jsonb NOT NULL,
      CONSTRAINT manuscript_numbering_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_manuscript_numbering_tenant_id ON manuscript_numbering(tenant_id)")
    op.execute("ALTER TABLE manuscript_numbering ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_numbering FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON manuscript_numbering "
        "USING(tenant_id=current_setting('app.tenant_id')::uuid)"
    )
    op.execute(
        "CREATE POLICY repository_read ON manuscript_numbering FOR SELECT "
        "USING(tenant_id=(SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_numbering")
