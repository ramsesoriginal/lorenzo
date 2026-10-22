"""Explicit clocks, readings and reckonings (ADR 0320)."""

from alembic import op

revision = "c03200000001"
down_revision = "c03190000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE FUNCTION clock_range_valid(v jsonb) RETURNS boolean
      LANGUAGE plpgsql IMMUTABLE STRICT AS $$
      DECLARE ln numeric; ld numeric; hn numeric; hd numeric;
      BEGIN
        IF jsonb_typeof(v) <> 'object' OR
          COALESCE(v->>'lo','') !~ '^-?[0-9]{1,38}(/[1-9][0-9]{0,37})?$' OR
          COALESCE(v->>'hi','') !~ '^-?[0-9]{1,38}(/[1-9][0-9]{0,37})?$' OR
          jsonb_typeof(v->'lo_inclusive') IS DISTINCT FROM 'boolean' OR
          jsonb_typeof(v->'hi_inclusive') IS DISTINCT FROM 'boolean' THEN RETURN false; END IF;
        ln := split_part(v->>'lo','/',1)::numeric;
        ld := COALESCE(NULLIF(split_part(v->>'lo','/',2),''),'1')::numeric;
        hn := split_part(v->>'hi','/',1)::numeric;
        hd := COALESCE(NULLIF(split_part(v->>'hi','/',2),''),'1')::numeric;
        RETURN ln*hd < hn*ld OR (ln*hd = hn*ld AND
          (v->>'lo_inclusive')::boolean AND (v->>'hi_inclusive')::boolean);
      EXCEPTION WHEN OTHERS THEN RETURN false;
      END $$""")
    op.execute("""CREATE TABLE clock (
      entity_id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      ticking boolean NOT NULL DEFAULT true, updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT clock_entity_tenant_key UNIQUE(entity_id,tenant_id),
      CONSTRAINT clock_ticking_key UNIQUE(entity_id,tenant_id,ticking),
      CONSTRAINT clock_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    for table, source, target in [
        ("event_clock_reading", "event_entity_id", "story_event"),
        ("calendar_reckoning", "calendar_entity_id", "calendar"),
    ]:
        op.execute(f"""CREATE TABLE {table} (
          {source} uuid NOT NULL, clock_entity_id uuid NOT NULL,
          tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
          ticking boolean NOT NULL DEFAULT true, data jsonb NOT NULL,
          is_shared boolean NOT NULL DEFAULT false, updated_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY({source},clock_entity_id),
          CONSTRAINT {table}_ticking CHECK(ticking),
          CONSTRAINT {table}_{"event" if table == "event_clock_reading" else "calendar"}_fkey
            FOREIGN KEY({source},tenant_id) REFERENCES {target}(entity_id,tenant_id)
            ON DELETE NO ACTION,
          CONSTRAINT {table}_clock_fkey FOREIGN KEY(clock_entity_id,tenant_id,ticking)
            REFERENCES clock(entity_id,tenant_id,ticking) ON DELETE NO ACTION)""")
    op.execute(
        "ALTER TABLE event_clock_reading ADD CONSTRAINT event_clock_reading_range "
        "CHECK(clock_range_valid(data))"
    )
    for table in ["clock", "event_clock_reading", "calendar_reckoning"]:
        op.execute(f"CREATE INDEX ix_{table}_tenant_id ON {table}(tenant_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
        )

        op.execute(
            f"CREATE POLICY repository_read ON {table} FOR SELECT "
            "USING(tenant_id = (SELECT repository_read_tenant_id()))"
        )
    op.execute("""ALTER TABLE calendar_reckoning ADD CONSTRAINT calendar_reckoning_reading
        CHECK(clock_range_valid(jsonb_build_object('lo',data->'reading','hi',data->'reading',
          'lo_inclusive',true,'hi_inclusive',true)))""")
    op.execute("""CREATE FUNCTION calendar_clock_mapping_guard() RETURNS trigger
      LANGUAGE plpgsql AS $$
      DECLARE old_map jsonb; new_map jsonb;
      BEGIN
        IF EXISTS(SELECT 1 FROM calendar_reckoning WHERE calendar_entity_id=NEW.entity_id
            AND tenant_id=NEW.tenant_id) THEN
          SELECT jsonb_agg(jsonb_build_array(s->'key',s->'days',s->'when')) INTO old_map
            FROM jsonb_array_elements(OLD.definition->'segments') s;
          SELECT jsonb_agg(jsonb_build_array(s->'key',s->'days',s->'when')) INTO new_map
            FROM jsonb_array_elements(NEW.definition->'segments') s;
          IF old_map IS DISTINCT FROM new_map THEN
            RAISE EXCEPTION 'Resolve calendar reckonings before changing day mapping'
              USING ERRCODE='23514', CONSTRAINT='calendar_clock_mapping';
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER calendar_clock_mapping_guard BEFORE UPDATE OF definition
      ON calendar
      FOR EACH ROW EXECUTE FUNCTION calendar_clock_mapping_guard()""")


def downgrade() -> None:
    op.execute("DROP TRIGGER calendar_clock_mapping_guard ON calendar")
    op.execute("DROP FUNCTION calendar_clock_mapping_guard()")
    for table in ["calendar_reckoning", "event_clock_reading", "clock"]:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION clock_range_valid(jsonb)")
