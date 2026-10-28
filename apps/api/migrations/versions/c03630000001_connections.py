"""Connections: an entry that joins two entries (ADR 0363)."""

from alembic import op

revision = "c03630000001"
down_revision = "c03620000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE connection (
      entity_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      end_a uuid NOT NULL, end_b uuid NOT NULL, one_way boolean NULL,
      CONSTRAINT connection_entity_tenant_key UNIQUE(entity_id,tenant_id),
      CONSTRAINT connection_ends_differ CHECK(end_a <> end_b),
      CONSTRAINT connection_one_way_true CHECK(one_way IS NOT FALSE),
      CONSTRAINT connection_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT connection_end_a_fkey FOREIGN KEY(end_a,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT connection_end_b_fkey FOREIGN KEY(end_b,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_connection_end_a ON connection(tenant_id, end_a)")
    op.execute("CREATE INDEX ix_connection_end_b ON connection(tenant_id, end_b)")
    op.execute("CREATE INDEX ix_connection_tenant_id ON connection(tenant_id)")
    op.execute("ALTER TABLE connection ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE connection FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON connection "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )
    op.execute(
        "CREATE POLICY repository_read ON connection FOR SELECT "
        "USING(tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE connection")
