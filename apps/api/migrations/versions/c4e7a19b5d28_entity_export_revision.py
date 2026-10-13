"""the revision of a tenant's entity export (ADR 0262)

tenant.export_revision is a counter that moves once for every transaction that writes a row the
bulk entity export shows: the entry and its kinds, link name, parents, own stat values and stat
groups, information, its payloads and who knows it. It is bumped by a constraint trigger on each
of those tables, deferred to commit, so a writer holds the tenant row for the length of its
commit and not for the length of its transaction (no deadlock with another writer's row locks),
and at most once per transaction.

Revision ID: c4e7a19b5d28
Revises: f9b3d6e8a2c4
Create Date: 2026-10-11 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e7a19b5d28"
down_revision: str | None = "f9b3d6e8a2c4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Every table whose rows the export shows, or that decides which rows a caller may see.
_TABLES = (
    "entity",
    "item",
    "item_instance",
    "being",
    "character",
    "entity_slug",
    "entity_prototype",
    "entity_stat",
    "entity_stat_group",
    "information",
    "payload",
    "payload_description",
    "payload_number",
    "payload_picture",
    "payload_document",
    "knowledge",
)


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("export_revision", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
    )
    # The marker is a transaction-local setting, reset by a rollback to a savepoint along with
    # the update it stands for.
    op.execute(
        """
        CREATE FUNCTION bump_export_revision() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            tid uuid;
            marker text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                tid := OLD.tenant_id;
            ELSE
                tid := NEW.tenant_id;
            END IF;
            marker := 'lorenzo.export_rev_' || replace(tid::text, '-', '');
            IF coalesce(current_setting(marker, true), '') = '' THEN
                UPDATE tenant SET export_revision = export_revision + 1 WHERE id = tid;
                PERFORM set_config(marker, '1', true);
            END IF;
            RETURN NULL;
        END
        $$
        """
    )
    for table in _TABLES:
        op.execute(
            f'CREATE CONSTRAINT TRIGGER "{table}_export_revision" '
            f'AFTER INSERT OR UPDATE OR DELETE ON "{table}" '
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION bump_export_revision()"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f'DROP TRIGGER "{table}_export_revision" ON "{table}"')
    op.execute("DROP FUNCTION bump_export_revision()")
    op.drop_column("tenant", "export_revision")
