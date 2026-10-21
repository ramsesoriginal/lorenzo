"""All beings may join groups; retry receipts for Event participant snapshots (ADR 0316)."""

from alembic import op

revision = "c03160000002"
down_revision = "c03160000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE group_member DROP CONSTRAINT group_member_character_entity_id_fkey")
    op.execute(
        "ALTER TABLE group_member ADD CONSTRAINT group_member_character_entity_id_fkey "
        "FOREIGN KEY(character_entity_id,tenant_id) "
        "REFERENCES being(entity_id,tenant_id) ON DELETE CASCADE"
    )
    op.execute("""CREATE TABLE event_group_creation (
        group_entity_id uuid PRIMARY KEY,
        tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
        created_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
        request_hash text NOT NULL,
        CONSTRAINT event_group_creation_tenant_key UNIQUE(group_entity_id,tenant_id),
        CONSTRAINT event_group_creation_group_fkey FOREIGN KEY(group_entity_id,tenant_id)
          REFERENCES entity(id,tenant_id) ON DELETE CASCADE
    )""")
    op.execute("CREATE INDEX ix_event_group_creation_tenant_id ON event_group_creation(tenant_id)")
    op.execute(
        "CREATE INDEX ix_event_group_creation_created_by ON event_group_creation(created_by)"
    )
    op.execute("ALTER TABLE event_group_creation ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE event_group_creation FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON event_group_creation "
        "USING(tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM group_member gm LEFT JOIN character c
        ON c.entity_id=gm.character_entity_id AND c.tenant_id=gm.tenant_id
        WHERE c.entity_id IS NULL)
      THEN RAISE EXCEPTION 'Remove NPC group memberships before downgrade'; END IF;
    END $$""")
    op.execute("DROP TABLE event_group_creation")
    op.execute("ALTER TABLE group_member DROP CONSTRAINT group_member_character_entity_id_fkey")
    op.execute(
        "ALTER TABLE group_member ADD CONSTRAINT group_member_character_entity_id_fkey "
        "FOREIGN KEY(character_entity_id,tenant_id) "
        "REFERENCES character(entity_id,tenant_id) ON DELETE CASCADE"
    )
