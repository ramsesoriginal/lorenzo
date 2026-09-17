"""notification batch id

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-17 14:05:13.980183

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ADR 0057 - one value shared by every row a single POST .../
    # notifications call fans out, so a sender can pull "everyone I sent
    # this to" in one query instead of correlating by title/timestamp.
    # server_default backfills any pre-existing row (none in practice, this
    # table is new this same branch) with its own random value - every row
    # from a single INSERT still needs its *own* explicit, shared value,
    # which is set application-side (lorenzo_api/notifications.py), not by
    # this default.
    op.add_column(
        "notification",
        sa.Column(
            "batch_id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
    )
    op.create_index(op.f("ix_notification_batch_id"), "notification", ["batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_batch_id"), table_name="notification")
    op.drop_column("notification", "batch_id")
