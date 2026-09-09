"""membership rls allows self access for GET /me

Revision ID: 8d9ec377f48a
Revises: 8b1772ba94a9
Create Date: 2026-09-09 01:27:05.227052

"""

from collections.abc import Sequence

from alembic import op

revision: str = "8d9ec377f48a"
down_revision: str | None = "8b1772ba94a9"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# GET /me (ADR 0023) lists every tenant a caller belongs to - deliberately
# not tenant-scoped, so there's no single app.tenant_id to set for that
# query. NULLIF(..., '')::uuid, not a bare cast: a custom GUC set with
# is_local=true doesn't revert to genuinely NULL once its transaction
# ends, only to '' (empty string) - confirmed empirically, on a pooled
# connection previously used for a real tenant-scoped request this is the
# *common* case, not an edge case, so a bare current_setting(name, true)
# ::uuid would intermittently fail to cast in real production traffic, not
# just in tests. NULLIF folds both "genuinely never set" (NULL) and
# "set, then its transaction ended" ('') into the same safe NULL. Only
# membership's policy changes this way - every other RLS-protected table
# keeps the stricter, hard-failing single-argument current_setting(name).
_NEW_USING = (
    "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid "
    "OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid"
)
_OLD_USING = "tenant_id = current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    op.execute(f"ALTER POLICY tenant_isolation ON membership USING ({_NEW_USING})")


def downgrade() -> None:
    op.execute(f"ALTER POLICY tenant_isolation ON membership USING ({_OLD_USING})")
