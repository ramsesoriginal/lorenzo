"""grant rules: what a source entitles a holder to, and what a feature needs (ADR 0455)

`grant_rule` (on a source entry: a mode, a count, an option category, how long it lasts),
`grant_rule_condition` (a comparison of the holder or the source), `grant_rule_option` (an explicit
option, in order) and `feature_prerequisite` (a comparison on the holder that every rule offering
the feature respects). Every key is composite with tenant_id (ADR 0117), every table is repository
content (ADR 0118: tenant_isolation, repository_read) with FORCE ROW LEVEL
SECURITY. A rule goes with
its source entry and its category entry, an option with its entry, a prerequisite with the feature
kind; a stat a rule or a feature reads is not deleted (the API refuses).

Revision ID: d0455a0b0c0d
Revises: d0454a0b0c0d
Create Date: 2026-11-12 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d0455a0b0c0d"
down_revision: str | None = "d0454a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLES = ("grant_rule", "grant_rule_condition", "grant_rule_option", "feature_prerequisite")
_RLS = """
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {t} USING (tenant_id = current_setting('app.tenant_id')::uuid);
CREATE POLICY repository_read ON {t} FOR SELECT
  USING (tenant_id = (SELECT repository_read_tenant_id()))
"""


def upgrade() -> None:
    op.execute("""CREATE TABLE grant_rule (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      entry_id uuid NOT NULL,
      label text NULL,
      position integer NOT NULL,
      mode text NOT NULL,
      min_count integer NOT NULL DEFAULT 0,
      max_count integer NULL,
      count_stat_definition_id uuid NULL,
      option_category_entry_id uuid NULL,
      lasts text NOT NULL DEFAULT 'while_source',
      changeable boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT grant_rule_id_tenant_id_key UNIQUE (id, tenant_id),
      CONSTRAINT grant_rule_mode CHECK (mode IN ('all', 'choose')),
      CONSTRAINT grant_rule_lasts CHECK (lasts IN ('while_source', 'permanent')),
      CONSTRAINT grant_rule_min_count CHECK (min_count >= 0),
      CONSTRAINT grant_rule_max_count CHECK (max_count IS NULL OR max_count >= 1),
      CONSTRAINT grant_rule_min_within_max CHECK (max_count IS NULL OR min_count <= max_count),
      CONSTRAINT grant_rule_count_of_mode CHECK (
        (mode = 'choose' AND num_nonnulls(max_count, count_stat_definition_id) = 1)
        OR (mode = 'all' AND num_nonnulls(max_count, count_stat_definition_id) = 0
            AND min_count = 0 AND NOT changeable)),
      CONSTRAINT grant_rule_entry_id_fkey FOREIGN KEY (entry_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT grant_rule_count_stat_definition_id_fkey
        FOREIGN KEY (count_stat_definition_id, tenant_id)
        REFERENCES stat_definition(id, tenant_id),
      CONSTRAINT grant_rule_option_category_entry_id_fkey
        FOREIGN KEY (option_category_entry_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_grant_rule_tenant_id ON grant_rule(tenant_id)")
    op.execute("CREATE INDEX ix_grant_rule_entry_id ON grant_rule(entry_id)")
    op.execute(
        "CREATE INDEX ix_grant_rule_count_stat_definition_id "
        "ON grant_rule(count_stat_definition_id)"
    )
    op.execute(
        "CREATE INDEX ix_grant_rule_option_category_entry_id "
        "ON grant_rule(option_category_entry_id)"
    )
    op.execute("""CREATE TABLE grant_rule_condition (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      rule_id uuid NOT NULL,
      position integer NOT NULL,
      subject text NOT NULL,
      stat_definition_id uuid NOT NULL,
      comparator text NOT NULL,
      right_constant numeric NULL,
      right_stat_definition_id uuid NULL,
      CONSTRAINT grant_rule_condition_rule_id_position_key UNIQUE (rule_id, position),
      CONSTRAINT grant_rule_condition_subject CHECK (subject IN ('holder', 'source')),
      CONSTRAINT grant_rule_condition_comparator
        CHECK (comparator IN ('lt', 'le', 'eq', 'ne', 'ge', 'gt')),
      CONSTRAINT grant_rule_condition_one_right_side
        CHECK (num_nonnulls(right_stat_definition_id, right_constant) = 1),
      CONSTRAINT grant_rule_condition_rule_id_fkey FOREIGN KEY (rule_id, tenant_id)
        REFERENCES grant_rule(id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT grant_rule_condition_stat_definition_id_fkey
        FOREIGN KEY (stat_definition_id, tenant_id) REFERENCES stat_definition(id, tenant_id),
      CONSTRAINT grant_rule_condition_right_stat_definition_id_fkey
        FOREIGN KEY (right_stat_definition_id, tenant_id)
        REFERENCES stat_definition(id, tenant_id))""")
    op.execute("CREATE INDEX ix_grant_rule_condition_tenant_id ON grant_rule_condition(tenant_id)")
    op.execute("CREATE INDEX ix_grant_rule_condition_rule_id ON grant_rule_condition(rule_id)")
    op.execute(
        "CREATE INDEX ix_grant_rule_condition_stat_definition_id "
        "ON grant_rule_condition(stat_definition_id)"
    )
    op.execute(
        "CREATE INDEX ix_grant_rule_condition_right_stat_definition_id "
        "ON grant_rule_condition(right_stat_definition_id)"
    )
    op.execute("""CREATE TABLE grant_rule_option (
      rule_id uuid NOT NULL,
      option_entry_id uuid NOT NULL,
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      position integer NOT NULL,
      PRIMARY KEY (rule_id, option_entry_id),
      CONSTRAINT grant_rule_option_rule_id_position_key UNIQUE (rule_id, position),
      CONSTRAINT grant_rule_option_rule_id_fkey FOREIGN KEY (rule_id, tenant_id)
        REFERENCES grant_rule(id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT grant_rule_option_option_entry_id_fkey FOREIGN KEY (option_entry_id, tenant_id)
        REFERENCES entity(id, tenant_id) ON DELETE CASCADE)""")
    op.execute("CREATE INDEX ix_grant_rule_option_tenant_id ON grant_rule_option(tenant_id)")
    op.execute(
        "CREATE INDEX ix_grant_rule_option_option_entry_id ON grant_rule_option(option_entry_id)"
    )
    op.execute("""CREATE TABLE feature_prerequisite (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
      feature_id uuid NOT NULL,
      position integer NOT NULL,
      stat_definition_id uuid NOT NULL,
      comparator text NOT NULL,
      right_constant numeric NULL,
      right_stat_definition_id uuid NULL,
      CONSTRAINT feature_prerequisite_feature_id_position_key UNIQUE (feature_id, position),
      CONSTRAINT feature_prerequisite_comparator
        CHECK (comparator IN ('lt', 'le', 'eq', 'ne', 'ge', 'gt')),
      CONSTRAINT feature_prerequisite_one_right_side
        CHECK (num_nonnulls(right_stat_definition_id, right_constant) = 1),
      CONSTRAINT feature_prerequisite_feature_id_fkey FOREIGN KEY (feature_id, tenant_id)
        REFERENCES feature(entity_id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT feature_prerequisite_stat_definition_id_fkey
        FOREIGN KEY (stat_definition_id, tenant_id) REFERENCES stat_definition(id, tenant_id),
      CONSTRAINT feature_prerequisite_right_stat_definition_id_fkey
        FOREIGN KEY (right_stat_definition_id, tenant_id)
        REFERENCES stat_definition(id, tenant_id))""")
    op.execute("CREATE INDEX ix_feature_prerequisite_tenant_id ON feature_prerequisite(tenant_id)")
    op.execute(
        "CREATE INDEX ix_feature_prerequisite_feature_id ON feature_prerequisite(feature_id)"
    )
    op.execute(
        "CREATE INDEX ix_feature_prerequisite_stat_definition_id "
        "ON feature_prerequisite(stat_definition_id)"
    )
    op.execute(
        "CREATE INDEX ix_feature_prerequisite_right_stat_definition_id "
        "ON feature_prerequisite(right_stat_definition_id)"
    )
    for table in _TABLES:
        for statement in _RLS.format(t=table).strip().split(";\n"):
            op.execute(statement)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
