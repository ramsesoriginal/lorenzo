"""A fingerprint on every picture, and the pictures under a Map (ADR 0360, ADR 0361)."""

from alembic import op

revision = "c03620000001"
down_revision = "c03540000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Generated, so that no write path can leave it stale or forget it.
    op.execute(
        "ALTER TABLE payload_picture "
        "ADD COLUMN sha256 bytea GENERATED ALWAYS AS (sha256(data)) STORED"
    )
    op.execute("""CREATE TABLE map_layer (
      map_entity_id uuid NOT NULL, position smallint NOT NULL, information_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      calibration jsonb NULL, opacity double precision NULL, reviewed_sha256 bytea NULL,
      PRIMARY KEY (tenant_id, map_entity_id, position),
      CONSTRAINT map_layer_position_range CHECK(position BETWEEN 0 AND 7),
      CONSTRAINT map_layer_opacity_range CHECK(opacity IS NULL OR opacity BETWEEN 0 AND 1),
      CONSTRAINT map_layer_calibration_object
        CHECK(calibration IS NULL OR jsonb_typeof(calibration) = 'object'),
      CONSTRAINT map_layer_map_fkey FOREIGN KEY(map_entity_id,tenant_id)
        REFERENCES map(entity_id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT map_layer_information_fkey FOREIGN KEY(information_id,tenant_id)
        REFERENCES information(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_map_layer_information ON map_layer(tenant_id, information_id)")
    op.execute("CREATE INDEX ix_map_layer_tenant_id ON map_layer(tenant_id)")
    op.execute("ALTER TABLE map_layer ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE map_layer FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON map_layer "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )
    op.execute(
        "CREATE POLICY repository_read ON map_layer FOR SELECT "
        "USING(tenant_id = (SELECT repository_read_tenant_id()))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE map_layer")
    op.execute("ALTER TABLE payload_picture DROP COLUMN sha256")
