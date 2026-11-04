"""Personal manuscript-length goals (ADR 0383)."""

from alembic import op

revision = "c03830000001"
down_revision = "e1b6d4a9c370"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE manuscript_goal (
        tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
        entry_id uuid NOT NULL, author_id uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
        scope varchar NOT NULL, target_words integer, version integer NOT NULL,
        PRIMARY KEY(entry_id, author_id, scope),
        CONSTRAINT manuscript_goal_entry_fkey FOREIGN KEY(entry_id,tenant_id)
          REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
        CONSTRAINT manuscript_goal_scope CHECK(scope IN ('direct','assembled')),
        CONSTRAINT manuscript_goal_target CHECK(target_words BETWEEN 1 AND 100000000),
        CONSTRAINT manuscript_goal_version CHECK(version >= 1))""")
    op.execute("CREATE INDEX ix_manuscript_goal_tenant_id ON manuscript_goal(tenant_id)")
    op.execute("ALTER TABLE manuscript_goal ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE manuscript_goal FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON manuscript_goal "
        "USING(tenant_id=current_setting('app.tenant_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE manuscript_goal")
