"""Session planning and local appearances (ADR 0317)."""

from alembic import op

revision = "c03170000001"
down_revision = "c03160000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE player ADD CONSTRAINT player_campaign_tenant_key
        UNIQUE(id,campaign_id,tenant_id)
    """)
    op.execute("""
        ALTER TABLE character_player ADD CONSTRAINT character_player_tenant_key
        UNIQUE(character_entity_id,player_id,tenant_id)
    """)
    op.execute("""
        CREATE TABLE scene ( entity_id UUID NOT NULL, tenant_id UUID NOT NULL, period_entity_id
        UUID, PRIMARY KEY (entity_id), CONSTRAINT scene_tenant_key UNIQUE (entity_id,
        tenant_id), CONSTRAINT scene_entity_fkey FOREIGN KEY(entity_id, tenant_id) REFERENCES
        entity (id, tenant_id) ON DELETE CASCADE, CONSTRAINT scene_period_fkey FOREIGN
        KEY(period_entity_id, tenant_id) REFERENCES calendar_period (entity_id, tenant_id) ON
        DELETE NO ACTION, FOREIGN KEY(tenant_id) REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_scene_tenant_id ON scene (tenant_id)
    """)
    op.execute("""
        ALTER TABLE scene ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE scene FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON scene USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE POLICY repository_read ON scene FOR SELECT USING(tenant_id = (SELECT
        repository_read_tenant_id()))
    """)
    op.execute("""
        CREATE TABLE story_session ( entity_id UUID NOT NULL, tenant_id UUID NOT NULL,
        campaign_id UUID NOT NULL, real_date DATE, start_period_id UUID, PRIMARY KEY
        (entity_id), CONSTRAINT story_session_tenant_key UNIQUE (entity_id, tenant_id),
        CONSTRAINT story_session_campaign_key UNIQUE (entity_id, campaign_id, tenant_id),
        CONSTRAINT story_session_entity_fkey FOREIGN KEY(entity_id, tenant_id) REFERENCES entity
        (id, tenant_id) ON DELETE CASCADE, CONSTRAINT story_session_campaign_fkey FOREIGN
        KEY(campaign_id, tenant_id) REFERENCES campaign (id, tenant_id) ON DELETE NO ACTION,
        CONSTRAINT story_session_start_fkey FOREIGN KEY(start_period_id, tenant_id) REFERENCES
        calendar_period (entity_id, tenant_id) ON DELETE NO ACTION, FOREIGN KEY(tenant_id)
        REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_story_session_tenant_id ON story_session (tenant_id)
    """)
    op.execute("""
        ALTER TABLE story_session ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE story_session FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON story_session USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE TABLE session_gm ( session_entity_id UUID NOT NULL, user_id UUID NOT NULL,
        tenant_id UUID NOT NULL, PRIMARY KEY (session_entity_id, user_id), CONSTRAINT
        session_gm_session_fkey FOREIGN KEY(session_entity_id, tenant_id) REFERENCES
        story_session (entity_id, tenant_id) ON DELETE CASCADE, FOREIGN KEY(user_id) REFERENCES
        app_user (id) ON DELETE CASCADE, FOREIGN KEY(tenant_id) REFERENCES tenant (id) ON DELETE
        CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_session_gm_tenant_id ON session_gm (tenant_id)
    """)
    op.execute("""
        ALTER TABLE session_gm ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE session_gm FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON session_gm USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE TABLE session_player ( session_entity_id UUID NOT NULL, player_id UUID NOT NULL,
        tenant_id UUID NOT NULL, campaign_id UUID NOT NULL, PRIMARY KEY (session_entity_id,
        player_id), CONSTRAINT session_player_tenant_key UNIQUE (session_entity_id, player_id,
        tenant_id), CONSTRAINT session_player_session_fkey FOREIGN KEY(session_entity_id,
        campaign_id, tenant_id) REFERENCES story_session (entity_id, campaign_id, tenant_id) ON
        DELETE CASCADE, CONSTRAINT session_player_player_fkey FOREIGN KEY(player_id,
        campaign_id, tenant_id) REFERENCES player (id, campaign_id, tenant_id) ON DELETE
        CASCADE, FOREIGN KEY(tenant_id) REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_session_player_tenant_id ON session_player (tenant_id)
    """)
    op.execute("""
        ALTER TABLE session_player ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE session_player FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON session_player USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE TABLE session_character ( session_entity_id UUID NOT NULL, player_id UUID NOT
        NULL, character_entity_id UUID NOT NULL, tenant_id UUID NOT NULL, PRIMARY KEY
        (session_entity_id, player_id, character_entity_id), CONSTRAINT
        session_character_attendee_fkey FOREIGN KEY(session_entity_id, player_id, tenant_id)
        REFERENCES session_player (session_entity_id, player_id, tenant_id) ON DELETE CASCADE,
        CONSTRAINT session_character_character_fkey FOREIGN KEY(character_entity_id, player_id,
        tenant_id) REFERENCES character_player (character_entity_id, player_id, tenant_id) ON
        DELETE CASCADE, FOREIGN KEY(tenant_id) REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_session_character_tenant_id ON session_character (tenant_id)
    """)
    op.execute("""
        ALTER TABLE session_character ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE session_character FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON session_character USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE TABLE scene_appearance ( entity_id UUID NOT NULL, tenant_id UUID NOT NULL,
        session_entity_id UUID NOT NULL, scene_entity_id UUID NOT NULL, position INTEGER NOT
        NULL, is_shared BOOLEAN DEFAULT false NOT NULL, PRIMARY KEY (entity_id), CONSTRAINT
        scene_appearance_tenant_key UNIQUE (entity_id, tenant_id), CONSTRAINT
        scene_appearance_position_key UNIQUE (session_entity_id, position) DEFERRABLE INITIALLY
        DEFERRED, CONSTRAINT scene_appearance_position CHECK (position >= 0), CONSTRAINT
        scene_appearance_entity_fkey FOREIGN KEY(entity_id, tenant_id) REFERENCES entity (id,
        tenant_id) ON DELETE CASCADE, CONSTRAINT scene_appearance_session_fkey FOREIGN
        KEY(session_entity_id, tenant_id) REFERENCES story_session (entity_id, tenant_id) ON
        DELETE NO ACTION, CONSTRAINT scene_appearance_scene_fkey FOREIGN KEY(scene_entity_id,
        tenant_id) REFERENCES scene (entity_id, tenant_id) ON DELETE NO ACTION, FOREIGN
        KEY(tenant_id) REFERENCES tenant (id) ON DELETE CASCADE )
    """)
    op.execute("""
        CREATE INDEX ix_scene_appearance_tenant_id ON scene_appearance (tenant_id)
    """)
    op.execute("""
        ALTER TABLE scene_appearance ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE scene_appearance FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON scene_appearance USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE scene_appearance
    """)
    op.execute("""
        DROP TABLE session_character
    """)
    op.execute("""
        DROP TABLE session_player
    """)
    op.execute("""
        DROP TABLE session_gm
    """)
    op.execute("""
        DROP TABLE story_session
    """)
    op.execute("""
        DROP TABLE scene
    """)
    op.execute("""
        ALTER TABLE character_player DROP CONSTRAINT character_player_tenant_key
    """)
    op.execute("""
        ALTER TABLE player DROP CONSTRAINT player_campaign_tenant_key
    """)
