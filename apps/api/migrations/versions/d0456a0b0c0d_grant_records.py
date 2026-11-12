"""grant records: how a holder came to have a feature (ADR 0456)

`grant_record` (a holder, the rule and the source a grant was made from, the feature, the instance
while it is active, and `revoked` with a reason when it is not). Every key is composite with
tenant_id (ADR 0117); the table is repository content (ADR 0118: tenant_isolation, repository_read)
with FORCE ROW LEVEL SECURITY. One active record for a (holder, rule, source, feature), and one
for an instance. A record goes with its holder, feature and instance; a deleted source entry or rule
leaves its row, with no source or no rule (an award reads like that).

Revision ID: d0456a0b0c0d
Revises: d0455a0b0c0d
Create Date: 2026-11-12 22:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d0456a0b0c0d"
down_revision: str | None = "d0455a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_RLS = """
ALTER TABLE grant_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE grant_record FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON grant_record
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
CREATE POLICY repository_read ON grant_record FOR SELECT
  USING (tenant_id = (SELECT repository_read_tenant_id()))
"""


def upgrade() -> None:
    op.execute("""CREATE TABLE grant_record (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      holder_id uuid NOT NULL,
      rule_id uuid NULL,
      source_ref_id uuid NULL,
      feature_id uuid NOT NULL,
      feature_instance_id uuid NULL,
      state text NOT NULL DEFAULT 'active',
      revoked_reason text NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      created_by uuid NULL REFERENCES app_user(id) ON DELETE SET NULL,
      CONSTRAINT grant_record_state CHECK (state IN ('active', 'revoked')),
      CONSTRAINT grant_record_revoked_reason
        CHECK (revoked_reason IS NULL OR revoked_reason IN ('source', 'conditions', 'removed')),
      CONSTRAINT grant_record_active_has_one
        CHECK (state = 'revoked' OR feature_instance_id IS NOT NULL),
      CONSTRAINT grant_record_reason_if_revoked
        CHECK ((state = 'revoked') = (revoked_reason IS NOT NULL)),
      CONSTRAINT grant_record_holder_id_fkey FOREIGN KEY (holder_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT grant_record_rule_id_fkey FOREIGN KEY (rule_id, tenant_id)
        REFERENCES grant_rule(id, tenant_id) ON DELETE SET NULL (rule_id),
      CONSTRAINT grant_record_source_ref_id_fkey FOREIGN KEY (source_ref_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE SET NULL (source_ref_id),
      CONSTRAINT grant_record_feature_id_fkey FOREIGN KEY (feature_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT grant_record_feature_instance_id_fkey FOREIGN KEY (feature_instance_id, tenant_id)
        REFERENCES feature_instance(entity_id, tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_grant_record_tenant_id ON grant_record(tenant_id)")
    op.execute("CREATE INDEX ix_grant_record_holder_id ON grant_record(holder_id)")
    op.execute("CREATE INDEX ix_grant_record_rule_id ON grant_record(rule_id)")
    op.execute("CREATE INDEX ix_grant_record_source_ref_id ON grant_record(source_ref_id)")
    op.execute("CREATE INDEX ix_grant_record_feature_id ON grant_record(feature_id)")
    op.execute("CREATE INDEX ix_grant_record_created_by ON grant_record(created_by)")
    op.execute(
        "CREATE UNIQUE INDEX grant_record_active_once "
        "ON grant_record(holder_id, rule_id, source_ref_id, feature_id) "
        "WHERE state = 'active' AND rule_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX grant_record_instance_once "
        "ON grant_record(feature_instance_id) WHERE feature_instance_id IS NOT NULL"
    )
    for statement in _RLS.strip().split(";\n"):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE grant_record")
