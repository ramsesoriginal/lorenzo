"""Placement: an entry is at a Location (ADR 0333)."""

from alembic import op

revision = "c03330000001"
down_revision = "c03300000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE entity_location (
      entity_id uuid PRIMARY KEY, location_entity_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      CONSTRAINT entity_location_distinct CHECK(entity_id <> location_entity_id),
      CONSTRAINT entity_location_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT entity_location_location_fkey FOREIGN KEY(location_entity_id,tenant_id)
        REFERENCES location(entity_id,tenant_id) ON DELETE CASCADE)""")
    op.execute(
        "CREATE INDEX ix_entity_location_place ON entity_location"
        "(tenant_id, location_entity_id, entity_id)"
    )
    op.execute("CREATE INDEX ix_entity_location_tenant_id ON entity_location(tenant_id)")
    op.execute("ALTER TABLE entity_location ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE entity_location FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON entity_location "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )
    op.execute(
        "CREATE POLICY repository_read ON entity_location FOR SELECT "
        "USING(tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE entity_location")
