"""Maps and their placements (ADR 0336)."""

from alembic import op

revision = "c03360000001"
down_revision = "c03330000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE map (
      entity_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      system jsonb NOT NULL, subject_entity_id uuid NULL,
      CONSTRAINT map_entity_tenant_key UNIQUE(entity_id,tenant_id),
      CONSTRAINT map_system_object CHECK(jsonb_typeof(system) = 'object'),
      CONSTRAINT map_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT map_subject_fkey FOREIGN KEY(subject_entity_id,tenant_id)
        REFERENCES location(entity_id,tenant_id) ON DELETE SET NULL (subject_entity_id))""")
    op.execute("""CREATE TABLE map_placement (
      map_entity_id uuid NOT NULL, entry_entity_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      geometry jsonb NOT NULL, role text NULL, style jsonb NULL,
      z smallint NOT NULL DEFAULT 0, bytes integer NOT NULL,
      minx double precision NOT NULL, miny double precision NOT NULL,
      maxx double precision NOT NULL, maxy double precision NOT NULL,
      PRIMARY KEY (map_entity_id, entry_entity_id),
      CONSTRAINT map_placement_geometry_object CHECK(jsonb_typeof(geometry) = 'object'),
      CONSTRAINT map_placement_map_fkey FOREIGN KEY(map_entity_id,tenant_id)
        REFERENCES map(entity_id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT map_placement_entry_fkey FOREIGN KEY(entry_entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    # The page of a Map's placements: z, then entry, as ADR 0338 reads them.
    op.execute(
        "CREATE INDEX ix_map_placement_page ON map_placement"
        "(tenant_id, map_entity_id, z, entry_entity_id)"
    )
    op.execute("CREATE INDEX ix_map_placement_entry ON map_placement(tenant_id, entry_entity_id)")
    op.execute("CREATE INDEX ix_map_subject ON map(tenant_id, subject_entity_id)")
    for table in ["map", "map_placement"]:
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
    op.execute("DROP TABLE map_placement")
    op.execute("DROP TABLE map")
