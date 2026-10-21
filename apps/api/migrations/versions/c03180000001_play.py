"""Explicit Session and play order (ADR 0318)."""

from alembic import op

revision = "c03180000001"
down_revision = "c03170000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE scene_appearance ADD COLUMN play_status VARCHAR NOT NULL DEFAULT
        'planned', ADD COLUMN played_position INTEGER
    """)
    op.execute("""
        ALTER TABLE scene_appearance ADD CONSTRAINT scene_appearance_play_status CHECK
        (play_status IN ('planned','played','skipped')), ADD CONSTRAINT
        scene_appearance_play_shape CHECK ((play_status = 'played') = (played_position IS
        NOT NULL)), ADD CONSTRAINT scene_appearance_played_position CHECK (played_position
        IS NULL OR played_position >= 0), ADD CONSTRAINT
        scene_appearance_played_position_key UNIQUE (session_entity_id, played_position)
        DEFERRABLE INITIALLY DEFERRED
    """)
    op.execute("""
        CREATE TABLE session_sequence ( session_entity_id UUID PRIMARY KEY, tenant_id UUID
        NOT NULL REFERENCES tenant(id) ON DELETE CASCADE, campaign_id UUID NOT NULL,
        position INTEGER NOT NULL, CONSTRAINT session_sequence_session_fkey FOREIGN
        KEY(session_entity_id,campaign_id,tenant_id) REFERENCES
        story_session(entity_id,campaign_id,tenant_id) ON DELETE CASCADE, CONSTRAINT
        session_sequence_position_key UNIQUE(campaign_id,position) DEFERRABLE INITIALLY
        DEFERRED, CONSTRAINT session_sequence_position CHECK(position >= 0))
    """)
    op.execute("""
        CREATE TABLE event_presentation ( id UUID PRIMARY KEY, tenant_id UUID NOT NULL
        REFERENCES tenant(id) ON DELETE CASCADE, appearance_entity_id UUID NOT NULL,
        event_entity_id UUID NOT NULL, position INTEGER NOT NULL, is_shared BOOLEAN NOT NULL
        DEFAULT false, CONSTRAINT event_presentation_tenant_key UNIQUE(id,tenant_id),
        CONSTRAINT event_presentation_appearance_fkey FOREIGN
        KEY(appearance_entity_id,tenant_id) REFERENCES scene_appearance(entity_id,tenant_id)
        ON DELETE NO ACTION, CONSTRAINT event_presentation_event_fkey FOREIGN
        KEY(event_entity_id,tenant_id) REFERENCES story_event(entity_id,tenant_id) ON DELETE
        NO ACTION, CONSTRAINT event_presentation_position_key
        UNIQUE(appearance_entity_id,position) DEFERRABLE INITIALLY DEFERRED, CONSTRAINT
        event_presentation_position CHECK(position >= 0))
    """)
    op.execute("""
        CREATE INDEX ix_session_sequence_tenant_id ON session_sequence(tenant_id)
    """)
    op.execute("""
        ALTER TABLE session_sequence ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE session_sequence FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON session_sequence USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)
    op.execute("""
        CREATE INDEX ix_event_presentation_tenant_id ON event_presentation(tenant_id)
    """)
    op.execute("""
        ALTER TABLE event_presentation ENABLE ROW LEVEL SECURITY
    """)
    op.execute("""
        ALTER TABLE event_presentation FORCE ROW LEVEL SECURITY
    """)
    op.execute("""
        CREATE POLICY tenant_isolation ON event_presentation USING(tenant_id =
        current_setting('app.tenant_id')::uuid)
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE event_presentation
    """)
    op.execute("""
        DROP TABLE session_sequence
    """)
    op.execute("""
        ALTER TABLE scene_appearance DROP CONSTRAINT scene_appearance_played_position_key,
        DROP CONSTRAINT scene_appearance_played_position, DROP CONSTRAINT
        scene_appearance_play_shape, DROP CONSTRAINT scene_appearance_play_status, DROP
        COLUMN played_position, DROP COLUMN play_status
    """)
