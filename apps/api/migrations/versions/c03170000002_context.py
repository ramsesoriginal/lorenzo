"""Scene and Session references (ADR 0317)."""

from alembic import op

revision = "c03170000002"
down_revision = "c03170000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE scene_fact ( scene_entity_id UUID NOT NULL, fact_entity_id UUID NOT NULL,
        tenant_id UUID NOT NULL, is_shared BOOLEAN DEFAULT false NOT NULL, PRIMARY KEY
        (scene_entity_id, fact_entity_id), CONSTRAINT scene_fact_source_fkey FOREIGN
        KEY(scene_entity_id, tenant_id) REFERENCES scene (entity_id, tenant_id) ON DELETE
        CASCADE, CONSTRAINT scene_fact_target_fkey FOREIGN KEY(fact_entity_id, tenant_id)
        REFERENCES fact (entity_id, tenant_id) ON DELETE NO ACTION, FOREIGN KEY(tenant_id)
        REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_scene_fact_tenant_id ON scene_fact (tenant_id)
    """)
    op.execute("""
        ALTER TABLE scene_fact ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE scene_fact FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON scene_fact USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE POLICY repository_read ON scene_fact FOR SELECT USING(tenant_id = (SELECT
        repository_read_tenant_id()))
    """)
    op.execute("""
        CREATE TABLE scene_event ( scene_entity_id UUID NOT NULL, event_entity_id UUID NOT NULL,
        tenant_id UUID NOT NULL, is_shared BOOLEAN DEFAULT false NOT NULL, PRIMARY KEY
        (scene_entity_id, event_entity_id), CONSTRAINT scene_event_source_fkey FOREIGN
        KEY(scene_entity_id, tenant_id) REFERENCES scene (entity_id, tenant_id) ON DELETE
        CASCADE, CONSTRAINT scene_event_target_fkey FOREIGN KEY(event_entity_id, tenant_id)
        REFERENCES story_event (entity_id, tenant_id) ON DELETE NO ACTION, FOREIGN
        KEY(tenant_id) REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_scene_event_tenant_id ON scene_event (tenant_id)
    """)
    op.execute("""
        ALTER TABLE scene_event ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE scene_event FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON scene_event USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE POLICY repository_read ON scene_event FOR SELECT USING(tenant_id = (SELECT
        repository_read_tenant_id()))
    """)
    op.execute("""
        CREATE TABLE scene_being ( scene_entity_id UUID NOT NULL, being_entity_id UUID NOT NULL,
        tenant_id UUID NOT NULL, is_shared BOOLEAN DEFAULT false NOT NULL, PRIMARY KEY
        (scene_entity_id, being_entity_id), CONSTRAINT scene_being_source_fkey FOREIGN
        KEY(scene_entity_id, tenant_id) REFERENCES scene (entity_id, tenant_id) ON DELETE
        CASCADE, CONSTRAINT scene_being_target_fkey FOREIGN KEY(being_entity_id, tenant_id)
        REFERENCES being (entity_id, tenant_id) ON DELETE NO ACTION, FOREIGN KEY(tenant_id)
        REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_scene_being_tenant_id ON scene_being (tenant_id)
    """)
    op.execute("""
        ALTER TABLE scene_being ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE scene_being FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON scene_being USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE POLICY repository_read ON scene_being FOR SELECT USING(tenant_id = (SELECT
        repository_read_tenant_id()))
    """)
    op.execute("""
        CREATE TABLE session_fact ( session_entity_id UUID NOT NULL, fact_entity_id UUID NOT
        NULL, tenant_id UUID NOT NULL, is_shared BOOLEAN DEFAULT false NOT NULL, PRIMARY KEY
        (session_entity_id, fact_entity_id), CONSTRAINT session_fact_source_fkey FOREIGN
        KEY(session_entity_id, tenant_id) REFERENCES story_session (entity_id, tenant_id) ON
        DELETE CASCADE, CONSTRAINT session_fact_target_fkey FOREIGN KEY(fact_entity_id,
        tenant_id) REFERENCES fact (entity_id, tenant_id) ON DELETE NO ACTION, FOREIGN
        KEY(tenant_id) REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_session_fact_tenant_id ON session_fact (tenant_id)
    """)
    op.execute("""
        ALTER TABLE session_fact ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE session_fact FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON session_fact USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE TABLE session_event ( session_entity_id UUID NOT NULL, event_entity_id UUID NOT
        NULL, tenant_id UUID NOT NULL, is_shared BOOLEAN DEFAULT false NOT NULL, PRIMARY KEY
        (session_entity_id, event_entity_id), CONSTRAINT session_event_source_fkey FOREIGN
        KEY(session_entity_id, tenant_id) REFERENCES story_session (entity_id, tenant_id) ON
        DELETE CASCADE, CONSTRAINT session_event_target_fkey FOREIGN KEY(event_entity_id,
        tenant_id) REFERENCES story_event (entity_id, tenant_id) ON DELETE NO ACTION, FOREIGN
        KEY(tenant_id) REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_session_event_tenant_id ON session_event (tenant_id)
    """)
    op.execute("""
        ALTER TABLE session_event ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE session_event FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON session_event USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE session_event")
    op.execute("DROP TABLE session_fact")
    op.execute("DROP TABLE scene_being")
    op.execute("DROP TABLE scene_event")
    op.execute("DROP TABLE scene_fact")
