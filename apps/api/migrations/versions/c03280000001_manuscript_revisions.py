"""Designated manuscripts and transaction checkpoints (ADR 0328)."""

from alembic import op

revision = "c03280000001"
down_revision = "c03210000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("INSERT INTO information_type VALUES ('manuscript', true, 'gm_authored')")
    op.execute("DROP INDEX information_singleton_type")
    op.execute("""CREATE UNIQUE INDEX information_singleton_type ON information(entity_id,type)
      WHERE type IN ('description','main_picture','manuscript')""")
    op.execute("""CREATE TABLE manuscript_revision (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      information_id uuid NOT NULL, transaction_id bigint NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(), snapshot jsonb NOT NULL,
      CONSTRAINT manuscript_revision_information_fkey FOREIGN KEY(information_id,tenant_id)
        REFERENCES information(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_revision_transaction_key UNIQUE(information_id,transaction_id))""")
    op.execute("CREATE INDEX ix_manuscript_revision_tenant_id ON manuscript_revision(tenant_id)")
    op.execute("""CREATE INDEX ix_manuscript_revision_information_id
      ON manuscript_revision(information_id)""")
    op.execute("ALTER TABLE manuscript_revision ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_revision FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON manuscript_revision
      USING(tenant_id=current_setting('app.tenant_id')::uuid)""")
    op.execute("""CREATE FUNCTION checkpoint_manuscript() RETURNS trigger
      LANGUAGE plpgsql AS $$
      DECLARE info_id uuid; bundle information%ROWTYPE; elements jsonb;
      BEGIN
        IF TG_OP='UPDATE' AND to_jsonb(OLD)=to_jsonb(NEW) THEN RETURN NEW; END IF;
        IF TG_TABLE_NAME='payload' THEN
          IF TG_OP='UPDATE' AND OLD.information_id=NEW.information_id
            AND OLD."order"=NEW."order" THEN RETURN NEW; END IF;
          info_id := CASE WHEN TG_OP='DELETE' THEN OLD.information_id ELSE NEW.information_id END;
        ELSE
          SELECT information_id INTO info_id FROM payload WHERE id=
            CASE WHEN TG_OP='DELETE' THEN OLD.payload_id ELSE NEW.payload_id END;
        END IF;
        SELECT * INTO bundle FROM information WHERE id=info_id AND type='manuscript' FOR UPDATE;
        IF NOT FOUND THEN RETURN COALESCE(NEW,OLD); END IF;
        -- Initial bundle construction (including repository copies) has no previous saved state.
        IF EXISTS(SELECT 1 FROM information WHERE id=info_id
          AND xmin::text::bigint=txid_current() % 4294967296
          AND created_at=transaction_timestamp())
          THEN RETURN COALESCE(NEW,OLD); END IF;
        IF EXISTS(SELECT 1 FROM manuscript_revision
          WHERE information_id=info_id AND transaction_id=txid_current())
          THEN RETURN COALESCE(NEW,OLD); END IF;
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
          'id',p.id, 'order',p."order", 'description',to_jsonb(d),
          'picture',CASE WHEN pic.payload_id IS NULL THEN NULL ELSE
            jsonb_build_object('data',encode(pic.data,'base64'),'file_type',pic.file_type) END,
          'number',to_jsonb(n), 'document',to_jsonb(doc)) ORDER BY p."order",p.id),'[]'::jsonb)
          INTO elements FROM payload p
          LEFT JOIN payload_description d ON d.payload_id=p.id
          LEFT JOIN payload_picture pic ON pic.payload_id=p.id
          LEFT JOIN payload_number n ON n.payload_id=p.id
          LEFT JOIN payload_document doc ON doc.payload_id=p.id
          WHERE p.information_id=info_id AND p.tenant_id=bundle.tenant_id
            AND (d.payload_id IS NOT NULL OR pic.payload_id IS NOT NULL
              OR n.payload_id IS NOT NULL OR doc.payload_id IS NOT NULL);
        IF elements='[]'::jsonb THEN RETURN COALESCE(NEW,OLD); END IF;
        INSERT INTO manuscript_revision(tenant_id,information_id,transaction_id,snapshot)
          VALUES(bundle.tenant_id,info_id,txid_current(),
            jsonb_build_object('title',bundle.title,'payloads',elements))
          ON CONFLICT(information_id,transaction_id) DO NOTHING;
        RETURN COALESCE(NEW,OLD);
      END $$""")
    for table in (
        "payload",
        "payload_description",
        "payload_picture",
        "payload_number",
        "payload_document",
    ):
        op.execute(f"""CREATE TRIGGER manuscript_checkpoint BEFORE INSERT OR UPDATE OR DELETE
          ON {table} FOR EACH ROW EXECUTE FUNCTION checkpoint_manuscript()""")


def downgrade() -> None:
    for table in (
        "payload",
        "payload_description",
        "payload_picture",
        "payload_number",
        "payload_document",
    ):
        op.execute(f"DROP TRIGGER manuscript_checkpoint ON {table}")
    op.execute("DROP FUNCTION checkpoint_manuscript()")
    op.execute("DROP TABLE manuscript_revision")
    op.execute("DELETE FROM information_type WHERE name='manuscript'")
    op.execute("DROP INDEX information_singleton_type")
    op.execute("""CREATE UNIQUE INDEX information_singleton_type ON information(entity_id,type)
      WHERE type IN ('description','main_picture')""")
