"""Explicit Event ordering assertions and race-safe cycle prevention (ADR 0312)."""

from collections.abc import Sequence

from alembic import op

revision: str = "c03120000001"
down_revision: str | None = "c03110000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE event_relationship (
      from_event_id uuid NOT NULL, to_event_id uuid NOT NULL, kind text NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      PRIMARY KEY(from_event_id,to_event_id,kind),
      CONSTRAINT event_relationship_distinct CHECK(from_event_id <> to_event_id),
      CONSTRAINT event_relationship_kind CHECK(kind IN ('order','causes')),
      CONSTRAINT event_relationship_from_fkey FOREIGN KEY(from_event_id,tenant_id)
        REFERENCES story_event(entity_id,tenant_id) ON DELETE NO ACTION
        DEFERRABLE INITIALLY DEFERRED,
      CONSTRAINT event_relationship_to_fkey FOREIGN KEY(to_event_id,tenant_id)
        REFERENCES story_event(entity_id,tenant_id) ON DELETE NO ACTION
        DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("CREATE INDEX ix_event_relationship_tenant_id ON event_relationship(tenant_id)")
    op.execute("CREATE INDEX ix_event_relationship_to_event_id ON event_relationship(to_event_id)")
    op.execute("ALTER TABLE event_relationship ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE event_relationship FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON event_relationship
      USING(tenant_id = current_setting('app.tenant_id')::uuid)""")
    op.execute("""CREATE POLICY repository_read ON event_relationship FOR SELECT
      USING(tenant_id = (SELECT repository_read_tenant_id()))""")
    op.execute("""CREATE FUNCTION event_relationship_guard() RETURNS trigger
      LANGUAGE plpgsql VOLATILE SECURITY INVOKER AS $$
      DECLARE t uuid;
      BEGIN
        IF TG_OP = 'DELETE' THEN t := OLD.tenant_id; ELSE t := NEW.tenant_id; END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended('lorenzo:event-order:' || t::text, 0));
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        IF TG_OP = 'UPDATE' THEN
          RAISE EXCEPTION 'Remove and add an Event relationship to change it'
            USING ERRCODE = '23514', CONSTRAINT = 'event_relationship_immutable';
        END IF;
        IF EXISTS (
          WITH RECURSIVE later(id) AS (
            SELECT NEW.to_event_id
            UNION SELECT r.to_event_id FROM event_relationship r
              JOIN later l ON r.from_event_id=l.id
              WHERE r.tenant_id=NEW.tenant_id
          ) SELECT 1 FROM later WHERE id=NEW.from_event_id
        ) THEN
          RAISE EXCEPTION 'Event relationships must be acyclic'
            USING ERRCODE = '23514', CONSTRAINT = 'event_relationship_cycle';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER event_relationship_guard BEFORE INSERT OR UPDATE OR DELETE
      ON event_relationship FOR EACH ROW EXECUTE FUNCTION event_relationship_guard()""")


def downgrade() -> None:
    op.execute("DROP TABLE event_relationship")
    op.execute("DROP FUNCTION event_relationship_guard()")
