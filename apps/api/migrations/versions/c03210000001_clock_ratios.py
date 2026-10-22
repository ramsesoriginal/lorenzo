"""Constant exact clock relationships (ADR 0321)."""

from alembic import op

revision = "c03210000001"
down_revision = "c03200000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE FUNCTION clock_relation_valid(v jsonb) RETURNS boolean
      LANGUAGE plpgsql IMMUTABLE STRICT AS $$
      DECLARE point jsonb;
      BEGIN
        point := jsonb_build_object('lo',v->'ratio','hi',v->'ratio',
          'lo_inclusive',true,'hi_inclusive',true);
        IF NOT clock_range_valid(point) OR split_part(v->>'ratio','/',1)::numeric=0
          THEN RETURN false; END IF;
        IF (v->>'clock_anchor' IS NULL) <> (v->>'reference_anchor' IS NULL)
          THEN RETURN false; END IF;
        IF v->>'clock_anchor' IS NOT NULL THEN
          RETURN clock_range_valid(jsonb_build_object('lo',v->'clock_anchor','hi',v->'clock_anchor',
              'lo_inclusive',true,'hi_inclusive',true)) AND
            clock_range_valid(jsonb_build_object('lo',v->'reference_anchor',
              'hi',v->'reference_anchor','lo_inclusive',true,'hi_inclusive',true));
        END IF;
        RETURN true;
      EXCEPTION WHEN OTHERS THEN RETURN false;
      END $$""")
    op.execute("""CREATE TABLE clock_relationship (
      clock_entity_id uuid NOT NULL, reference_clock_entity_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      ticking boolean NOT NULL DEFAULT true, data jsonb NOT NULL,
      is_shared boolean NOT NULL DEFAULT false, updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(clock_entity_id,reference_clock_entity_id),
      CONSTRAINT clock_relationship_ticking CHECK(ticking),
      CONSTRAINT clock_relationship_canonical CHECK(clock_entity_id < reference_clock_entity_id),
      CONSTRAINT clock_relationship_definition CHECK(clock_relation_valid(data)),
      CONSTRAINT clock_relationship_clock_fkey FOREIGN KEY(clock_entity_id,tenant_id,ticking)
        REFERENCES clock(entity_id,tenant_id,ticking) ON DELETE NO ACTION,
      CONSTRAINT clock_relationship_reference_fkey
        FOREIGN KEY(reference_clock_entity_id,tenant_id,ticking)
        REFERENCES clock(entity_id,tenant_id,ticking) ON DELETE NO ACTION)""")
    op.execute("CREATE INDEX ix_clock_relationship_tenant_id ON clock_relationship(tenant_id)")
    op.execute("ALTER TABLE clock_relationship ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clock_relationship FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON clock_relationship
      USING(tenant_id = current_setting('app.tenant_id')::uuid)""")
    op.execute("""CREATE POLICY repository_read ON clock_relationship FOR SELECT
      USING(tenant_id = (SELECT repository_read_tenant_id()))""")


def downgrade() -> None:
    op.execute("DROP TABLE clock_relationship")
    op.execute("DROP FUNCTION clock_relation_valid(jsonb)")
