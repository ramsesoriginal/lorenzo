"""merge attribution and stat-resolution migration heads

Revision ID: d9746a3eaf87
Revises: c5af8be21a7f, 6341fedbfc47
Create Date: 2026-09-15 14:17:32.362108

"""

from collections.abc import Sequence

revision: str = "d9746a3eaf87"
down_revision: str | None = ("c5af8be21a7f", "6341fedbfc47")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
