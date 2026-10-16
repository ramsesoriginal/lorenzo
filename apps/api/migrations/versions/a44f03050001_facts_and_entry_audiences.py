"""New fact and audience tables only (ADR 0305); existing table policies are unchanged."""

from collections.abc import Sequence

from alembic import op

revision: str = "a44f03050001"
down_revision: str | None = "b9f3d5a7c1e2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
_TABLES = ("fact", "entity_audience", "entity_knowledge", "fact_about")


def upgrade() -> None:
    for statement in (
        """
CREATE TABLE fact (

            entity_id uuid PRIMARY KEY,

            tenant_id uuid NOT NULL

                REFERENCES tenant(id) ON DELETE CASCADE,

            CONSTRAINT fact_entity_id_tenant_id_key

                UNIQUE (entity_id, tenant_id),

            CONSTRAINT fact_entity_id_fkey FOREIGN KEY (entity_id, tenant_id)

                REFERENCES entity(id, tenant_id) ON DELETE CASCADE

        )
        """,
        """
CREATE INDEX ix_fact_tenant_id ON fact(tenant_id)
        """,
        """
CREATE TABLE entity_audience (

            entity_id uuid PRIMARY KEY,

            tenant_id uuid NOT NULL

                REFERENCES tenant(id) ON DELETE CASCADE,

            is_public boolean NOT NULL DEFAULT false, updated_at timestamptz NOT NULL DEFAULT now(),

            CONSTRAINT entity_audience_entity_id_tenant_id_key

                UNIQUE (entity_id, tenant_id),

            CONSTRAINT entity_audience_entity_id_fkey FOREIGN KEY (entity_id, tenant_id)

                REFERENCES entity(id, tenant_id) ON DELETE CASCADE

        )
        """,
        """
CREATE INDEX ix_entity_audience_tenant_id ON entity_audience(tenant_id)
        """,
        """
CREATE TABLE entity_knowledge (

            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

            tenant_id uuid NOT NULL

                REFERENCES tenant(id) ON DELETE CASCADE,

            entity_id uuid NOT NULL, knower_entity_id uuid, knower_player_id uuid,

            CONSTRAINT entity_knowledge_entity_id_fkey FOREIGN KEY (entity_id, tenant_id)

                REFERENCES entity_audience(entity_id, tenant_id) ON DELETE CASCADE,

            CONSTRAINT entity_knowledge_knower_entity_id_fkey

                FOREIGN KEY (knower_entity_id, tenant_id)

                REFERENCES entity(id, tenant_id) ON DELETE CASCADE,

            CONSTRAINT entity_knowledge_knower_player_id_fkey

                FOREIGN KEY (knower_player_id, tenant_id)

                REFERENCES player(id, tenant_id) ON DELETE CASCADE,

            CONSTRAINT entity_knowledge_exactly_one_knower

                CHECK (num_nonnulls(knower_entity_id, knower_player_id) = 1),

            CONSTRAINT entity_knowledge_unique_entity_knower

                UNIQUE (entity_id, knower_entity_id),

            CONSTRAINT entity_knowledge_unique_player_knower

                UNIQUE (entity_id, knower_player_id))
        """,
        """
CREATE INDEX ix_entity_knowledge_tenant_id ON entity_knowledge(tenant_id)
        """,
        """
CREATE INDEX ix_entity_knowledge_entity_id ON entity_knowledge(entity_id)
        """,
        """
CREATE INDEX ix_entity_knowledge_knower_entity_id ON entity_knowledge(knower_entity_id)
        """,
        """
CREATE INDEX ix_entity_knowledge_knower_player_id ON entity_knowledge(knower_player_id)
        """,
        """
CREATE TABLE fact_about (

            fact_entity_id uuid NOT NULL, subject_entity_id uuid NOT NULL,

            tenant_id uuid NOT NULL

                REFERENCES tenant(id) ON DELETE CASCADE,

            PRIMARY KEY (fact_entity_id, subject_entity_id),

            CONSTRAINT fact_about_fact_entity_id_fkey FOREIGN KEY (fact_entity_id, tenant_id)

                REFERENCES fact(entity_id, tenant_id) ON DELETE CASCADE,

            CONSTRAINT fact_about_subject_entity_id_fkey FOREIGN KEY (subject_entity_id, tenant_id)

                REFERENCES entity(id, tenant_id) ON DELETE CASCADE

        )
        """,
        """
CREATE INDEX ix_fact_about_tenant_id ON fact_about(tenant_id)
        """,
        """
CREATE INDEX ix_fact_about_subject_entity_id ON fact_about(subject_entity_id)
        """,
    ):
        op.execute(statement)
    for table in _TABLES:
        op.execute(
            f'CREATE CONSTRAINT TRIGGER "{table}_export_revision" '
            f'AFTER INSERT OR UPDATE OR DELETE ON "{table}" '
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION bump_export_revision()"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
        op.execute(
            f"CREATE POLICY repository_read ON {table} FOR SELECT "
            "USING (tenant_id = (SELECT repository_read_tenant_id()))"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_table(table)
