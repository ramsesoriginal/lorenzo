"""Books, Editions and Chapter composition (ADR 0341)."""

from alembic import op

revision = "c03360000001"
down_revision = "c03280000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("book", "chapter", "edition"):
        extra = (
            ", book_entity_id uuid NOT NULL, CONSTRAINT edition_book_fkey "
            "FOREIGN KEY(book_entity_id,tenant_id) REFERENCES book(entity_id,tenant_id)"
            if table == "edition"
            else ""
        )
        op.execute(f"""CREATE TABLE {table} (
          entity_id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
          CONSTRAINT {table}_tenant_key UNIQUE(entity_id,tenant_id),
          CONSTRAINT {table}_entity_fkey
          FOREIGN KEY(entity_id,tenant_id)
          REFERENCES entity(id,tenant_id) ON DELETE CASCADE
          {extra})""")
    op.execute("""CREATE TABLE manuscript_placement (
      chapter_entity_id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      parent_entity_id uuid NOT NULL, before_payload_id uuid, position integer NOT NULL,
      CONSTRAINT manuscript_placement_not_self CHECK(parent_entity_id<>chapter_entity_id),
      CONSTRAINT manuscript_placement_parent_fkey
          FOREIGN KEY(parent_entity_id,tenant_id)
          REFERENCES entity(id,tenant_id),
      CONSTRAINT manuscript_placement_chapter_fkey
          FOREIGN KEY(chapter_entity_id,tenant_id)
          REFERENCES chapter(entity_id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT manuscript_placement_payload_fkey
          FOREIGN KEY(before_payload_id,tenant_id)
          REFERENCES payload(id,tenant_id))""")
    for table in ("book", "edition", "chapter", "manuscript_placement"):
        op.execute(f"CREATE INDEX ix_{table}_tenant_id ON {table}(tenant_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING(tenant_id=current_setting('app.tenant_id')::uuid)"
        )
        op.execute(f"""CREATE POLICY repository_read ON {table} FOR SELECT USING (
          tenant_id = (SELECT repository_read_tenant_id()))""")
    op.execute("""CREATE FUNCTION detach_manuscript_anchor() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        UPDATE manuscript_placement SET before_payload_id=NULL WHERE before_payload_id=OLD.id;
        RETURN OLD;
      END $$""")
    op.execute(
        "CREATE TRIGGER detach_manuscript_anchor BEFORE DELETE ON payload "
        "FOR EACH ROW EXECUTE FUNCTION detach_manuscript_anchor()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER detach_manuscript_anchor ON payload")
    op.execute("DROP FUNCTION detach_manuscript_anchor()")
    for table in ("manuscript_placement", "edition", "chapter", "book"):
        op.execute(f"DROP TABLE {table}")
