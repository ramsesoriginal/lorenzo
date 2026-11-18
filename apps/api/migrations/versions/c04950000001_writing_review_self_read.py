"""A reviewer may read their own review grants in every tenant (ADR 0508).

`GET /me/writing-reviews` lists the Editions shared with the caller across libraries, so it asks
for the caller's own `writing_review_grant` rows before any one tenant is set, as `GET /tenants`
does for memberships. A second, select-only policy admits exactly those rows. The tenant policy
changes only in how it reads the setting: with none set, or an empty one left on a pooled
connection, it matches nothing instead of failing the uuid cast (the NULLIF of a22dc991a926).
"""

from alembic import op

revision = "c04950000001"
down_revision = "e03980462006"
branch_labels = None
depends_on = None


_TENANT = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_OLD_TENANT = "tenant_id = current_setting('app.tenant_id')::uuid"


def upgrade() -> None:
    op.execute(f"ALTER POLICY tenant_isolation ON writing_review_grant USING ({_TENANT})")
    op.execute(
        "CREATE POLICY self_read ON writing_review_grant FOR SELECT "
        "USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY self_read ON writing_review_grant")
    op.execute(f"ALTER POLICY tenant_isolation ON writing_review_grant USING ({_OLD_TENANT})")
