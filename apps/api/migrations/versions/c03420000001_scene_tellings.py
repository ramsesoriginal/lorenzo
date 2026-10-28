"""Scene tellings, writing biographies and mixed placement (ADR 0342)."""

from alembic import op

revision = "c03420000001"
down_revision = "c03360000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE manuscript_placement DROP CONSTRAINT manuscript_placement_chapter_fkey")
    op.execute(
        "ALTER TABLE manuscript_placement RENAME COLUMN chapter_entity_id TO child_entity_id"
    )
    op.execute("""ALTER TABLE manuscript_placement
      ADD CONSTRAINT manuscript_placement_child_fkey
      FOREIGN KEY(child_entity_id,tenant_id) REFERENCES entity(id,tenant_id) ON DELETE CASCADE""")
    op.execute("""CREATE TABLE scene_telling (
      entity_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      scene_entity_id uuid NOT NULL, viewpoint_entity_id uuid,
      uses_scene_manuscript boolean NOT NULL DEFAULT true,
      CONSTRAINT scene_telling_tenant_key UNIQUE(entity_id,tenant_id),
      CONSTRAINT scene_telling_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT scene_telling_scene_fkey FOREIGN KEY(scene_entity_id,tenant_id)
        REFERENCES scene(entity_id,tenant_id),
      CONSTRAINT scene_telling_viewpoint_fkey FOREIGN KEY(viewpoint_entity_id,tenant_id)
        REFERENCES being(entity_id,tenant_id))""")
    op.execute("""CREATE TABLE writing_biography (
      entity_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      CONSTRAINT writing_biography_being_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES being(entity_id,tenant_id) ON DELETE CASCADE)""")
    for table in ("scene_telling", "writing_biography"):
        op.execute(f"CREATE INDEX ix_{table}_tenant_id ON {table}(tenant_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING(tenant_id=current_setting('app.tenant_id')::uuid)"
        )
        op.execute(
            f"CREATE POLICY repository_read ON {table} FOR SELECT "
            "USING(tenant_id=(SELECT repository_read_tenant_id()))"
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM manuscript_placement "
        "WHERE child_entity_id IN (SELECT entity_id FROM scene_telling)"
    )
    op.execute("DROP TABLE writing_biography")
    op.execute("DROP TABLE scene_telling")
    op.execute("ALTER TABLE manuscript_placement DROP CONSTRAINT manuscript_placement_child_fkey")
    op.execute(
        "ALTER TABLE manuscript_placement RENAME COLUMN child_entity_id TO chapter_entity_id"
    )
    op.execute("""ALTER TABLE manuscript_placement
      ADD CONSTRAINT manuscript_placement_chapter_fkey
      FOREIGN KEY(chapter_entity_id,tenant_id)
      REFERENCES chapter(entity_id,tenant_id) ON DELETE CASCADE""")
