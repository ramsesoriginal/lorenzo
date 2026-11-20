"""A being's recent stat changes, for the History of its sheet (ADR 0525)."""

from alembic import op

revision = "c05240000001"
down_revision = "c04950000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE entity_stat_change (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      entity_id uuid NOT NULL,
      stat_definition_id uuid NOT NULL,
      old_value jsonb, new_value jsonb,
      actor_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      CONSTRAINT entity_stat_change_entity_fkey FOREIGN KEY(entity_id,tenant_id)
        REFERENCES entity(id,tenant_id) ON DELETE CASCADE,
      CONSTRAINT entity_stat_change_stat_definition_fkey
        FOREIGN KEY(stat_definition_id,tenant_id)
        REFERENCES stat_definition(id,tenant_id) ON DELETE CASCADE)""")
    for column in ("tenant_id", "entity_id", "actor_id"):
        op.execute(f"CREATE INDEX ix_entity_stat_change_{column} ON entity_stat_change({column})")
    op.execute(
        "CREATE INDEX ix_entity_stat_change_entity_recent "
        "ON entity_stat_change(entity_id, created_at DESC)"
    )
    op.execute("ALTER TABLE entity_stat_change ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE entity_stat_change FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON entity_stat_change
      USING(tenant_id=current_setting('app.tenant_id')::uuid)""")


def downgrade() -> None:
    op.execute("DROP TABLE entity_stat_change")
