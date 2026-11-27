"""A person's preferences in their account, and their saved views of lists (ADR 0532)

app_user.preferences: the appearance a person chose (theme, density, motion), kept with the user
and not a tenant. saved_view: a view of a list kept by name, per library and per person, so it has
a tenant_id and the same row-level security as every tenant table (ADR 0002).
"""

from alembic import op

revision = "c05320000001"
down_revision = "c05300000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app_user ADD COLUMN preferences jsonb NOT NULL DEFAULT '{}'::jsonb")
    op.execute("""CREATE TABLE saved_view (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      user_id uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
      app text NOT NULL, list text NOT NULL, name text NOT NULL,
      query jsonb NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT saved_view_name_key UNIQUE (tenant_id, user_id, app, list, name))""")
    op.execute("CREATE INDEX ix_saved_view_tenant_id ON saved_view(tenant_id)")
    op.execute("CREATE INDEX ix_saved_view_user_id ON saved_view(user_id)")
    op.execute("ALTER TABLE saved_view ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE saved_view FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON saved_view
      USING(tenant_id=current_setting('app.tenant_id')::uuid)""")


def downgrade() -> None:
    op.execute("DROP TABLE saved_view")
    op.execute("ALTER TABLE app_user DROP COLUMN preferences")
