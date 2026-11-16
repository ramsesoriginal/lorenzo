"""templates: the `features` slot kind (ADR 0457)

A template slot may be of the kind `features`: the features the entry holds, grouped by type,
with a column for each stat of a group or a list, as a `held` slot has them. No table is added;
the check on `template_slot.kind` allows the new value.

Revision ID: d0457a0b0c0d
Revises: d0456a0b0c0d
Create Date: 2026-11-12 23:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d0457a0b0c0d"
down_revision: str | None = "d0456a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("template_slot_kind", "template_slot")
    op.create_check_constraint(
        "template_slot_kind",
        "template_slot",
        "kind IN ('stats', 'information', 'held', 'tags', 'features')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM template_slot WHERE kind = 'features'")
    op.drop_constraint("template_slot_kind", "template_slot")
    op.create_check_constraint(
        "template_slot_kind", "template_slot", "kind IN ('stats', 'information', 'held', 'tags')"
    )
