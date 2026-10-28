"""Frames and axes: an entry is a frame on an axis, and is on a frame (ADR 0369)."""

from alembic import op

revision = "c03690000001"
down_revision = "c03630000001"
branch_labels = None
depends_on = None

_POLICY = "tenant_id = current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    op.execute("""CREATE TABLE frame (
      entity_id uuid NOT NULL, axis text NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      CONSTRAINT frame_pkey PRIMARY KEY (entity_id, axis),
      CONSTRAINT frame_entity_tenant_axis_key UNIQUE (entity_id, tenant_id, axis),
      CONSTRAINT frame_axis_format CHECK (axis ~ '^[a-z][a-z0-9_]{0,31}$'),
      CONSTRAINT frame_entity_fkey FOREIGN KEY (entity_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE)""")
    op.execute("""CREATE TABLE entity_frame (
      entity_id uuid NOT NULL, axis text NOT NULL, frame_entity_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      CONSTRAINT entity_frame_pkey PRIMARY KEY (entity_id, axis),
      CONSTRAINT entity_frame_distinct CHECK (entity_id <> frame_entity_id),
      CONSTRAINT entity_frame_axis_format CHECK (axis ~ '^[a-z][a-z0-9_]{0,31}$'),
      CONSTRAINT entity_frame_entity_fkey FOREIGN KEY (entity_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT entity_frame_frame_fkey FOREIGN KEY (frame_entity_id, tenant_id, axis)
        REFERENCES frame(entity_id, tenant_id, axis) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_frame_tenant_id ON frame(tenant_id)")
    op.execute("CREATE INDEX ix_entity_frame_tenant_id ON entity_frame(tenant_id)")
    op.execute(
        "CREATE INDEX ix_entity_frame_members ON entity_frame"
        "(tenant_id, frame_entity_id, axis, entity_id)"
    )
    for table in ("frame", "entity_frame"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({_POLICY})")
        op.execute(
            f"CREATE POLICY repository_read ON {table} FOR SELECT "
            "USING(tenant_id = (SELECT repository_read_tenant_id()))"
        )


def downgrade() -> None:
    op.execute("DROP TABLE entity_frame")
    op.execute("DROP TABLE frame")
