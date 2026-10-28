"""Book-scoped review grants and notes (ADR 0343)."""

from alembic import op

revision = "c03430000001"
down_revision = "c03420000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE writing_review_grant (
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      edition_id uuid NOT NULL,
      user_id uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
      PRIMARY KEY(edition_id,user_id),
      CONSTRAINT writing_review_grant_edition_fkey FOREIGN KEY(edition_id,tenant_id)
        REFERENCES edition(entity_id,tenant_id) ON DELETE CASCADE)""")
    op.execute("""CREATE TABLE writing_review_note (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      edition_id uuid NOT NULL, entry_id uuid NOT NULL,
      author_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      content text NOT NULL, version integer NOT NULL DEFAULT 1,
      CONSTRAINT writing_review_note_edition_fkey FOREIGN KEY(edition_id,tenant_id)
        REFERENCES edition(entity_id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT writing_review_note_entry_fkey FOREIGN KEY(entry_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_writing_review_note_edition_id ON writing_review_note(edition_id)")
    for table in ("writing_review_grant", "writing_review_note"):
        op.execute(f"CREATE INDEX ix_{table}_tenant_id ON {table}(tenant_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING(tenant_id=current_setting('app.tenant_id')::uuid)"
        )


def downgrade() -> None:
    op.execute("DROP TABLE writing_review_note")
    op.execute("DROP TABLE writing_review_grant")
