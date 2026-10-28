"""Chapter joins and guarded source redirects (ADR 0348)."""

from alembic import op

revision = "c03480000001"
down_revision = "c03460000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_redirect (
      source_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      destination_id uuid, payload_id uuid, child_id uuid,
      CONSTRAINT manuscript_redirect_not_self CHECK(source_id <> destination_id),
      CONSTRAINT manuscript_redirect_one_anchor CHECK(payload_id IS NULL OR child_id IS NULL),
      CONSTRAINT manuscript_redirect_source_fkey FOREIGN KEY(source_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_redirect_destination_fkey FOREIGN KEY(destination_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE SET NULL (destination_id),
      CONSTRAINT manuscript_redirect_payload_fkey FOREIGN KEY(payload_id,tenant_id)
        REFERENCES payload(id,tenant_id) ON DELETE SET NULL (payload_id),
      CONSTRAINT manuscript_redirect_child_fkey FOREIGN KEY(child_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE SET NULL (child_id))""")
    op.execute("""CREATE TABLE manuscript_join (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      source_id uuid NOT NULL, destination_id uuid NOT NULL,
      actor_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      request_hash text NOT NULL, checkpoint jsonb NOT NULL,
      CONSTRAINT manuscript_join_source_fkey FOREIGN KEY(source_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_join_destination_fkey FOREIGN KEY(destination_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    for table, columns in (
        ("manuscript_redirect", ("tenant_id", "destination_id")),
        ("manuscript_join", ("tenant_id", "source_id", "destination_id")),
    ):
        for column in columns:
            op.execute(f"CREATE INDEX ix_{table}_{column} ON {table}({column})")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table}
          USING(tenant_id=current_setting('app.tenant_id')::uuid)""")
    op.execute("""CREATE POLICY repository_read ON manuscript_redirect FOR SELECT
      USING(tenant_id=(SELECT repository_read_tenant_id()))""")


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_join")
    op.execute("DROP TABLE manuscript_redirect")
