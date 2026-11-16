"""features: the kinds `feature` and `feature_instance` (ADR 0454)

`feature` (a marker with `repeatable` and `starts_inactive`) and `feature_instance` (a marker with
`active`). Both are keyed by the entry, with a same-tenant key into `entity` (ADR 0117), both are
repository content (ADR 0118: tenant_isolation, repository_read) with FORCE ROW LEVEL SECURITY.

Revision ID: d0454a0b0c0d
Revises: d0453a0b0c0d
Create Date: 2026-11-12 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d0454a0b0c0d"
down_revision: str | None = "d0453a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLES = ("feature", "feature_instance")
_RLS = """
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {t} USING (tenant_id = current_setting('app.tenant_id')::uuid);
CREATE POLICY repository_read ON {t} FOR SELECT
  USING (tenant_id = (SELECT repository_read_tenant_id()))
"""


def upgrade() -> None:
    op.execute("""CREATE TABLE feature (
      entity_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      repeatable boolean NOT NULL DEFAULT false,
      starts_inactive boolean NOT NULL DEFAULT false,
      CONSTRAINT feature_entity_id_tenant_id_key UNIQUE (entity_id, tenant_id),
      CONSTRAINT feature_entity_id_fkey FOREIGN KEY (entity_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_feature_tenant_id ON feature(tenant_id)")
    op.execute("""CREATE TABLE feature_instance (
      entity_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      active boolean NOT NULL DEFAULT true,
      CONSTRAINT feature_instance_entity_id_tenant_id_key UNIQUE (entity_id, tenant_id),
      CONSTRAINT feature_instance_entity_id_fkey FOREIGN KEY (entity_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_feature_instance_tenant_id ON feature_instance(tenant_id)")
    for table in _TABLES:
        for statement in _RLS.format(t=table).strip().split(";\n"):
            op.execute(statement)
    # A contents formula may keep the feature instances of a holder (ADR 0454).
    op.drop_constraint("computed_stat_contents_only_kind", "computed_stat_contents")
    op.create_check_constraint(
        "computed_stat_contents_only_kind",
        "computed_stat_contents",
        "only_kind IS NULL OR only_kind IN ('item_instance', 'feature_instance')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE computed_stat_contents SET only_kind = NULL WHERE only_kind = 'feature_instance'"
    )
    op.drop_constraint("computed_stat_contents_only_kind", "computed_stat_contents")
    op.create_check_constraint(
        "computed_stat_contents_only_kind",
        "computed_stat_contents",
        "only_kind IS NULL OR only_kind IN ('item_instance')",
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
