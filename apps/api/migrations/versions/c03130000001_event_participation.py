"""Event/Being participation association (ADR 0313)."""

from collections.abc import Sequence

from alembic import op

revision: str = "c03130000001"
down_revision: str | None = "c03120000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE event_participant (
        tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
        event_entity_id uuid NOT NULL, being_entity_id uuid NOT NULL,
        PRIMARY KEY(event_entity_id,being_entity_id),
        CONSTRAINT event_participant_event_fkey FOREIGN KEY(event_entity_id,tenant_id)
          REFERENCES story_event(entity_id,tenant_id) ON DELETE NO ACTION
          DEFERRABLE INITIALLY DEFERRED,
        CONSTRAINT event_participant_being_fkey FOREIGN KEY(being_entity_id,tenant_id)
          REFERENCES being(entity_id,tenant_id) ON DELETE NO ACTION
          DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("CREATE INDEX ix_event_participant_tenant_id ON event_participant(tenant_id)")
    op.execute(
        "CREATE INDEX ix_event_participant_being ON event_participant(being_entity_id,tenant_id)"
    )
    op.execute("ALTER TABLE event_participant ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE event_participant FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON event_participant
      USING(tenant_id = current_setting('app.tenant_id')::uuid)""")
    op.execute("""CREATE POLICY repository_read ON event_participant FOR SELECT
      USING(tenant_id = (SELECT repository_read_tenant_id()))""")


def downgrade() -> None:
    op.execute("DROP TABLE event_participant")
