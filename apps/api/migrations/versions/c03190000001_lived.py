"""Lived-before participation evidence and union graph integrity (ADR 0319)."""

from alembic import op

revision = "c03190000001"
down_revision = "c03180000001"
branch_labels = None
depends_on = None


def _guard(table: str, identity: str, *, lived: bool) -> None:
    assertions = """SELECT from_event_id, to_event_id FROM event_relationship
        WHERE tenant_id = NEW.tenant_id"""
    if lived:
        assertions += """ UNION SELECT from_event_id, to_event_id FROM lived_before
            WHERE tenant_id = NEW.tenant_id"""
    op.execute(f"""CREATE OR REPLACE FUNCTION {table}_guard() RETURNS trigger
        LANGUAGE plpgsql VOLATILE SECURITY INVOKER AS $$
        DECLARE t uuid;
        BEGIN
          IF TG_OP = 'DELETE' THEN t := OLD.tenant_id; ELSE t := NEW.tenant_id; END IF;
          PERFORM pg_advisory_xact_lock(hashtextextended('lorenzo:event-order:' || t::text, 0));
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          IF TG_OP = 'UPDATE' THEN
            IF {identity} THEN RETURN NEW; END IF;
            RAISE EXCEPTION 'Remove and add an assertion to change its identity'
              USING ERRCODE = '23514', CONSTRAINT = '{table}_immutable';
          END IF;
          IF EXISTS (
            WITH RECURSIVE edges(source, target) AS ({assertions}),
            later(id) AS (
              SELECT NEW.to_event_id UNION
              SELECT e.target FROM edges e JOIN later l ON e.source = l.id
            ) SELECT 1 FROM later WHERE id = NEW.from_event_id
          ) THEN
            RAISE EXCEPTION 'Event relationships must be acyclic'
              USING ERRCODE = '23514', CONSTRAINT = 'event_relationship_cycle';
          END IF;
          RETURN NEW;
        END $$""")


_RELATION_IDENTITY = """ROW(NEW.from_event_id, NEW.to_event_id, NEW.kind, NEW.tenant_id)
    IS NOT DISTINCT FROM ROW(OLD.from_event_id, OLD.to_event_id, OLD.kind, OLD.tenant_id)"""
_LIVED_IDENTITY = """ROW(NEW.from_event_id, NEW.to_event_id, NEW.being_entity_id, NEW.tenant_id)
    IS NOT DISTINCT FROM ROW(OLD.from_event_id, OLD.to_event_id,
                             OLD.being_entity_id, OLD.tenant_id)"""


def upgrade() -> None:
    op.execute("""
        CREATE TABLE lived_before (
          being_entity_id UUID NOT NULL, from_event_id UUID NOT NULL, to_event_id UUID NOT NULL,
          tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
          is_shared BOOLEAN NOT NULL DEFAULT false,
          PRIMARY KEY(being_entity_id, from_event_id, to_event_id),
          CONSTRAINT lived_before_tenant_key
            UNIQUE(being_entity_id, from_event_id, to_event_id, tenant_id),
          CONSTRAINT lived_before_from_participation_fkey
            FOREIGN KEY(from_event_id, being_entity_id, tenant_id)
            REFERENCES event_participant(event_entity_id, being_entity_id, tenant_id)
            ON DELETE NO ACTION,
          CONSTRAINT lived_before_to_participation_fkey
            FOREIGN KEY(to_event_id, being_entity_id, tenant_id)
            REFERENCES event_participant(event_entity_id, being_entity_id, tenant_id)
            ON DELETE NO ACTION,
          CONSTRAINT lived_before_distinct CHECK(from_event_id <> to_event_id))
    """)
    op.execute("CREATE INDEX ix_lived_before_tenant_id ON lived_before(tenant_id)")
    op.execute("ALTER TABLE lived_before ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lived_before FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON lived_before
        USING(tenant_id = current_setting('app.tenant_id')::uuid)""")
    op.execute("""CREATE POLICY repository_read ON lived_before FOR SELECT
        USING(tenant_id = (SELECT repository_read_tenant_id()))""")
    _guard("event_relationship", _RELATION_IDENTITY, lived=True)
    _guard("lived_before", _LIVED_IDENTITY, lived=True)
    op.execute("""CREATE TRIGGER lived_before_guard BEFORE INSERT OR UPDATE OR DELETE
        ON lived_before FOR EACH ROW EXECUTE FUNCTION lived_before_guard()""")


def downgrade() -> None:
    _guard("event_relationship", _RELATION_IDENTITY, lived=False)
    op.execute("DROP TABLE lived_before")
    op.execute("DROP FUNCTION lived_before_guard()")
