"""tenant.controllers_award_features (ADR 0467)

Whether the controller of a holder, and not only its manager, may award it a feature (RFC 0054
section 2, "where the library allows"). Off by default, so no library's behaviour changes until an
administrator turns it on.

Revision ID: d0461a0b0c0d
Revises: d0460a0b0c0d
Create Date: 2026-11-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0461a0b0c0d"
down_revision: str | None = "d0460a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column(
            "controllers_award_features",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant", "controllers_award_features")
