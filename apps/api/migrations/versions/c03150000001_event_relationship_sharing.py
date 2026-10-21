"""Explicit relationship sharing, private by default (ADR 0315)."""

from collections.abc import Sequence

from alembic import op

revision: str = "c03150000001"
down_revision: str | None = "c03140000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _guard(*, sharing: bool) -> None:
    update_guard = (
        """
        IF ROW(NEW.from_event_id, NEW.to_event_id, NEW.kind, NEW.tenant_id)
           IS NOT DISTINCT FROM ROW(OLD.from_event_id, OLD.to_event_id, OLD.kind, OLD.tenant_id)
        THEN RETURN NEW; END IF;
    """
        if sharing
        else ""
    )
    op.execute(f"""CREATE OR REPLACE FUNCTION event_relationship_guard() RETURNS trigger
      LANGUAGE plpgsql VOLATILE SECURITY INVOKER AS $$
      DECLARE t uuid;
      BEGIN
        IF TG_OP = 'DELETE' THEN t := OLD.tenant_id; ELSE t := NEW.tenant_id; END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended('lorenzo:event-order:' || t::text, 0));
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        IF TG_OP = 'UPDATE' THEN
          {update_guard}
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


def upgrade() -> None:
    op.execute("ALTER TABLE event_relationship ADD COLUMN is_shared boolean NOT NULL DEFAULT false")
    _guard(sharing=True)


def downgrade() -> None:
    _guard(sharing=False)
    op.execute("ALTER TABLE event_relationship DROP COLUMN is_shared")
