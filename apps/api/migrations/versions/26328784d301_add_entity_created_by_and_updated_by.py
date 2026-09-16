"""add entity created_by and updated_by

Revision ID: 26328784d301
Revises: 6b57c96d3505
Create Date: 2026-09-10 19:07:47.926013

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "26328784d301"
down_revision: str | None = "6b57c96d3505"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ADR 0029: nullable (an attribution can become unknown - the attributed
    # user deleting their own account - even though a timestamp never can),
    # ON DELETE SET NULL (losing the account clears attribution, doesn't
    # delete the entity). Covers item/item_instance/being for free - none of
    # the three ever exists independently of the entity row created
    # alongside it.
    op.add_column("entity", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.add_column("entity", sa.Column("updated_by", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_entity_created_by"), "entity", ["created_by"], unique=False)
    op.create_index(op.f("ix_entity_updated_by"), "entity", ["updated_by"], unique=False)
    op.create_foreign_key(
        "entity_created_by_fkey", "entity", "app_user", ["created_by"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "entity_updated_by_fkey", "entity", "app_user", ["updated_by"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("entity_updated_by_fkey", "entity", type_="foreignkey")
    op.drop_constraint("entity_created_by_fkey", "entity", type_="foreignkey")
    op.drop_index(op.f("ix_entity_updated_by"), table_name="entity")
    op.drop_index(op.f("ix_entity_created_by"), table_name="entity")
    op.drop_column("entity", "updated_by")
    op.drop_column("entity", "created_by")
