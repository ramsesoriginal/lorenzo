"""merge tenant creation and campaign CRUD attribution migrations

Revision ID: c5af8be21a7f
Revises: 9aa665f00305, 9ab3234c417c
Create Date: 2026-09-15 14:07:03.226359

"""

from collections.abc import Sequence

revision: str = "c5af8be21a7f"
down_revision: str | None = ("9aa665f00305", "9ab3234c417c")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
