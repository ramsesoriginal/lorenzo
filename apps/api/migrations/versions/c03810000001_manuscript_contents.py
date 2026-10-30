"""Structural contents settings (ADR 0381)."""

from alembic import op

revision = "c03810000001"
down_revision = "c03800000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_contents (
      entity_id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      settings jsonb NOT NULL,
      CONSTRAINT manuscript_contents_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_manuscript_contents_tenant_id ON manuscript_contents(tenant_id)")
    op.execute("ALTER TABLE manuscript_contents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_contents FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON manuscript_contents "
        "USING(tenant_id=current_setting('app.tenant_id')::uuid)"
    )
    op.execute(
        "CREATE POLICY repository_read ON manuscript_contents FOR SELECT "
        "USING(tenant_id=(SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_contents")
