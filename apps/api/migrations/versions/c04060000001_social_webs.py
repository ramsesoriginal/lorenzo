"""SocialWeb: a saved view of relationships, as an entry, with explicit members (ADR 0406)."""

from alembic import op

revision = "c04060000001"
down_revision = "c04050000001"
branch_labels = None
depends_on = None

_RLS = """
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {t} USING (tenant_id = current_setting('app.tenant_id')::uuid);
CREATE POLICY repository_read ON {t} FOR SELECT USING (tenant_id = (SELECT repository_read_tenant_id()))
"""


def upgrade() -> None:
    op.execute("""CREATE TABLE social_web (
      entity_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      layout text NOT NULL, layout_seed integer NOT NULL, theme_hint text NULL, view jsonb NULL,
      standing_stat_id uuid NULL, as_of_event uuid NULL,
      CONSTRAINT social_web_entity_tenant_key UNIQUE (entity_id, tenant_id),
      CONSTRAINT social_web_entity_fkey FOREIGN KEY (entity_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT social_web_standing_stat_id_fkey FOREIGN KEY (standing_stat_id, tenant_id)
        REFERENCES stat_definition(id, tenant_id) ON DELETE SET NULL (standing_stat_id),
      CONSTRAINT social_web_as_of_event_fkey FOREIGN KEY (as_of_event, tenant_id)
        REFERENCES story_event(entity_id, tenant_id) ON DELETE SET NULL (as_of_event))""")
    op.execute("CREATE INDEX ix_social_web_tenant_id ON social_web(tenant_id)")
    op.execute("""CREATE TABLE social_web_entry (
      web_entity_id uuid NOT NULL, entry_entity_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      x double precision NULL, y double precision NULL,
      PRIMARY KEY (web_entity_id, entry_entity_id),
      CONSTRAINT social_web_entry_position CHECK ((x IS NULL) = (y IS NULL)),
      CONSTRAINT social_web_entry_web_fkey FOREIGN KEY (web_entity_id, tenant_id)
        REFERENCES social_web(entity_id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT social_web_entry_entry_fkey FOREIGN KEY (entry_entity_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_social_web_entry_entry ON social_web_entry(tenant_id, entry_entity_id)")
    op.execute("CREATE INDEX ix_social_web_entry_tenant_id ON social_web_entry(tenant_id)")
    op.execute("""CREATE TABLE social_web_type (
      web_entity_id uuid NOT NULL, type_entity_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      PRIMARY KEY (web_entity_id, type_entity_id),
      CONSTRAINT social_web_type_web_fkey FOREIGN KEY (web_entity_id, tenant_id)
        REFERENCES social_web(entity_id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT social_web_type_type_fkey FOREIGN KEY (type_entity_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_social_web_type_tenant_id ON social_web_type(tenant_id)")
    for table in ("social_web", "social_web_entry", "social_web_type"):
        for statement in _RLS.format(t=table).strip().split(";\n"):
            op.execute(statement)


def downgrade() -> None:
    for table in ("social_web_type", "social_web_entry", "social_web"):
        op.execute(f"DROP TABLE {table}")
