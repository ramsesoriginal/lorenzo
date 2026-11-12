"""campaign.system_id: the game system a campaign plays (ADR 0452)

Nullable, a composite key with tenant_id (ADR 0117) to `system`; the free text `game_system`
stays the display name. Deleting a system a campaign names is refused by the API, so the key does
not clear anything.

Revision ID: d0452a0b0c0d
Revises: d0451a0b0c0d
Create Date: 2026-11-12 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0452a0b0c0d"
down_revision: str | None = "d0451a0b0c0d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaign", sa.Column("system_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "campaign_system_id_fkey",
        "campaign",
        "system",
        ["system_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_index("ix_campaign_system_id", "campaign", ["system_id"])


def downgrade() -> None:
    op.drop_index("ix_campaign_system_id", table_name="campaign")
    op.drop_constraint("campaign_system_id_fkey", "campaign", type_="foreignkey")
    op.drop_column("campaign", "system_id")
