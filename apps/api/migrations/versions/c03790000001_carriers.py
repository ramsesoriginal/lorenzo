"""Carriers and stable manuscript coverage (ADR 0379)."""

from alembic import op

revision = "c03790000001"
down_revision = "c03780000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE carrier (
      entity_id uuid PRIMARY KEY, tenant_id uuid NOT NULL
        REFERENCES tenant(id) ON DELETE CASCADE,
      CONSTRAINT carrier_tenant_key UNIQUE(entity_id,tenant_id),
      CONSTRAINT carrier_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("""CREATE TABLE carrier_coverage (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL
        REFERENCES tenant(id) ON DELETE CASCADE,
      carrier_id uuid NOT NULL, target_entity_id uuid, target_payload_id uuid,
      before_payload_id uuid, position integer NOT NULL,
      CONSTRAINT carrier_coverage_one_target 
        CHECK((target_entity_id IS NULL) <> (target_payload_id IS NULL)),
      CONSTRAINT carrier_coverage_carrier_fkey FOREIGN KEY(carrier_id,tenant_id)
        REFERENCES carrier(entity_id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT carrier_coverage_entry_fkey FOREIGN KEY(target_entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT carrier_coverage_payload_fkey FOREIGN KEY(target_payload_id,tenant_id)
        REFERENCES payload(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT carrier_coverage_anchor_fkey FOREIGN KEY(before_payload_id,tenant_id)
        REFERENCES payload(id,tenant_id) ON DELETE NO ACTION)""")
    op.execute("CREATE INDEX ix_carrier_coverage_carrier_id ON carrier_coverage(carrier_id)")
    for table in ("carrier", "carrier_coverage"):
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
    op.execute("""CREATE FUNCTION detach_carrier_anchor() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        UPDATE carrier_coverage SET before_payload_id=NULL WHERE before_payload_id=OLD.id;
        RETURN OLD;
      END $$""")
    op.execute(
        "CREATE TRIGGER detach_carrier_anchor BEFORE DELETE ON payload "
        "FOR EACH ROW EXECUTE FUNCTION detach_carrier_anchor()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER detach_carrier_anchor ON payload")
    op.execute("DROP FUNCTION detach_carrier_anchor()")
    op.execute("DROP TABLE carrier_coverage")
    op.execute("DROP TABLE carrier")
