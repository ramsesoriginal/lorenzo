"""Optional Event learning provenance (ADR 0314)."""

from collections.abc import Sequence

from alembic import op

revision: str = "c03140000001"
down_revision: str | None = "c03130000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE event_participant ADD CONSTRAINT event_participant_tenant_key "
        "UNIQUE(event_entity_id,being_entity_id,tenant_id)"
    )
    op.execute("""CREATE TABLE event_learning (
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      event_entity_id uuid NOT NULL, being_entity_id uuid NOT NULL, information_id uuid NOT NULL,
      PRIMARY KEY(event_entity_id,being_entity_id,information_id),
      UNIQUE(event_entity_id,being_entity_id,information_id,tenant_id),
      CONSTRAINT event_learning_participant_fkey
        FOREIGN KEY(event_entity_id,being_entity_id,tenant_id)
        REFERENCES event_participant(event_entity_id,being_entity_id,tenant_id)
        ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
      CONSTRAINT event_learning_information_fkey FOREIGN KEY(information_id,tenant_id)
        REFERENCES information(id,tenant_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("CREATE INDEX ix_event_learning_tenant_id ON event_learning(tenant_id)")
    op.execute("CREATE INDEX ix_event_learning_being ON event_learning(being_entity_id,tenant_id)")
    op.execute(
        "CREATE INDEX ix_event_learning_information ON event_learning(information_id,tenant_id)"
    )
    op.execute("ALTER TABLE event_learning ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE event_learning FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON event_learning
      USING(tenant_id = current_setting('app.tenant_id')::uuid)""")
    op.execute("""CREATE POLICY repository_read ON event_learning FOR SELECT
      USING(tenant_id = (SELECT repository_read_tenant_id()))""")


def downgrade() -> None:
    op.execute("DROP TABLE event_learning")
    op.execute("ALTER TABLE event_participant DROP CONSTRAINT event_participant_tenant_key")
