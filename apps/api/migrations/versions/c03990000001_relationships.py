"""Relationships: an entry that ties two entries (ADR 0399)."""

from alembic import op

revision = "c03990000001"
down_revision = "c03830000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE relationship (
      entity_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      end_a uuid NOT NULL, end_b uuid NOT NULL, one_way boolean NULL,
      CONSTRAINT relationship_entity_tenant_key UNIQUE(entity_id,tenant_id),
      CONSTRAINT relationship_ends_differ CHECK(end_a <> end_b),
      CONSTRAINT relationship_one_way_true CHECK(one_way IS NOT FALSE),
      CONSTRAINT relationship_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT relationship_end_a_fkey FOREIGN KEY(end_a,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT relationship_end_b_fkey FOREIGN KEY(end_b,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_relationship_end_a ON relationship(tenant_id, end_a)")
    op.execute("CREATE INDEX ix_relationship_end_b ON relationship(tenant_id, end_b)")
    op.execute("CREATE INDEX ix_relationship_tenant_id ON relationship(tenant_id)")
    op.execute("ALTER TABLE relationship ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE relationship FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON relationship "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )
    op.execute(
        "CREATE POLICY repository_read ON relationship FOR SELECT "
        "USING(tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE relationship")
