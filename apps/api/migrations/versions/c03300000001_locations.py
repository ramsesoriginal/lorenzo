"""Locations and their part-of tree (ADR 0330)."""

from alembic import op

revision = "c03300000001"
down_revision = "c03460000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE location (
      entity_id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      CONSTRAINT location_entity_tenant_key UNIQUE(entity_id,tenant_id),
      CONSTRAINT location_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("""CREATE TABLE location_part (
      child_entity_id uuid PRIMARY KEY, parent_entity_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      level_ordinal numeric NULL,
      CONSTRAINT location_part_distinct CHECK(child_entity_id <> parent_entity_id),
      CONSTRAINT location_part_child_fkey FOREIGN KEY(child_entity_id,tenant_id)
        REFERENCES location(entity_id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT location_part_parent_fkey FOREIGN KEY(parent_entity_id,tenant_id)
        REFERENCES location(entity_id,tenant_id) ON DELETE CASCADE)""")
    op.execute(
        "CREATE INDEX ix_location_part_parent ON location_part"
        "(tenant_id, parent_entity_id, level_ordinal, child_entity_id)"
    )
    for table in ["location", "location_part"]:
        op.execute(f"CREATE INDEX ix_{table}_tenant_id ON {table}(tenant_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
        )
        op.execute(
            f"CREATE POLICY repository_read ON {table} FOR SELECT "
            "USING(tenant_id = (SELECT repository_read_tenant_id()))"
        )


def downgrade() -> None:
    op.execute("DROP TABLE location_part")
    op.execute("DROP TABLE location")
