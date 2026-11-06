"""Relationship through: an authored, ordered chain of relationships (ADR 0402)."""

from alembic import op

revision = "c04020000001"
down_revision = "c04000000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE relationship_through (
      relationship_entity_id uuid NOT NULL,
      step smallint NOT NULL,
      via_entity_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      PRIMARY KEY (relationship_entity_id, step),
      CONSTRAINT relationship_through_via_key UNIQUE (relationship_entity_id, via_entity_id),
      CONSTRAINT relationship_through_not_self CHECK (relationship_entity_id <> via_entity_id),
      CONSTRAINT relationship_through_relationship_fkey
        FOREIGN KEY (relationship_entity_id, tenant_id)
        REFERENCES relationship(entity_id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT relationship_through_via_fkey FOREIGN KEY (via_entity_id, tenant_id)
        REFERENCES relationship(entity_id, tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_relationship_through_via ON relationship_through(tenant_id, via_entity_id)")
    op.execute("CREATE INDEX ix_relationship_through_tenant_id ON relationship_through(tenant_id)")
    op.execute("ALTER TABLE relationship_through ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE relationship_through FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON relationship_through "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )
    op.execute(
        "CREATE POLICY repository_read ON relationship_through FOR SELECT "
        "USING(tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE relationship_through")
