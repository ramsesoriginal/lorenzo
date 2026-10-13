"""one invite table, with kinds (ADR 0220)

campaign_invite becomes `invite`. A `kind` says what redeeming one does: `campaign` (every
row there is, so the default and the backfill), `tenant_role` (an Author or an Organizer
membership in a library or repository) or `library_access` (a grant of a repository to a
library). campaign_id and role become nullable and a check ties them to the kind: a campaign
link has a campaign and a role of player or gm, a role link has no campaign and a role of
author or orga, a library-access link has neither. A link that is not for a campaign always
has a use cap. The enum is renamed `invite_role` and gains author and orga.

The check compares the role as text: a value just added to an enum cannot be used in the
transaction that adds it, and the migrations of a new database run in one. Everything else
about the table is as it was: the hashed token, the required expiry, the use counter, the
two row-level-security policies (renamed), and the composite foreign key to the campaign,
which does not apply to a row with no campaign.

Revision ID: c4a2f7e91b35
Revises: a3c81d6e0f52
Create Date: 2026-10-08 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a2f7e91b35"
down_revision: str | None = "a3c81d6e0f52"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_KIND = sa.Enum("campaign", "tenant_role", "library_access", name="invite_kind")

_SHAPE = (
    "(kind::text = 'campaign' AND campaign_id IS NOT NULL"
    " AND role IS NOT NULL AND role::text IN ('player', 'gm'))"
    " OR (kind::text = 'tenant_role' AND campaign_id IS NULL"
    " AND role IS NOT NULL AND role::text IN ('author', 'orga'))"
    " OR (kind::text = 'library_access' AND campaign_id IS NULL AND role IS NULL)"
)
_CAPPED = "kind::text = 'campaign' OR max_uses IS NOT NULL"

# (old, new) for the objects a rename leaves with the old table's name.
_RENAMED = [
    ("campaign_invite_pkey", "invite_pkey"),
    ("campaign_invite_token_hash_key", "invite_token_hash_key"),
    ("ix_campaign_invite_tenant_id", "ix_invite_tenant_id"),
    ("ix_campaign_invite_campaign_id", "ix_invite_campaign_id"),
]
_RENAMED_CONSTRAINTS = [
    ("campaign_invite_max_uses", "invite_max_uses"),
    ("campaign_invite_tenant_id_fkey", "invite_tenant_id_fkey"),
    ("campaign_invite_created_by_fkey", "invite_created_by_fkey"),
    ("campaign_invite_campaign_id_fkey", "invite_campaign_id_fkey"),
]
_POLICIES = [
    ("campaign_invite_tenant", "invite_tenant"),
    ("campaign_invite_by_token", "invite_by_token"),
]


def upgrade() -> None:
    op.rename_table("campaign_invite", "invite")
    op.execute("ALTER TYPE campaign_invite_role RENAME TO invite_role")
    for old, new in _RENAMED:
        # The primary key and unique constraint's indexes carry their constraint's name.
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")
    for old, new in _RENAMED_CONSTRAINTS:
        op.execute(f"ALTER TABLE invite RENAME CONSTRAINT {old} TO {new}")
    for old, new in _POLICIES:
        op.execute(f"ALTER POLICY {old} ON invite RENAME TO {new}")

    op.execute("ALTER TYPE invite_role ADD VALUE IF NOT EXISTS 'author'")
    op.execute("ALTER TYPE invite_role ADD VALUE IF NOT EXISTS 'orga'")

    _KIND.create(op.get_bind())
    op.add_column("invite", sa.Column("kind", _KIND, server_default="campaign", nullable=False))
    op.alter_column("invite", "campaign_id", nullable=True)
    op.alter_column("invite", "role", nullable=True, server_default=None)
    op.create_check_constraint("invite_kind_shape", "invite", _SHAPE)
    op.create_check_constraint("invite_non_campaign_capped", "invite", _CAPPED)


def downgrade() -> None:
    # What only the wider table can hold goes: a role or a library link has no campaign.
    op.execute("DELETE FROM invite WHERE kind::text <> 'campaign'")
    op.drop_constraint("invite_non_campaign_capped", "invite")
    op.drop_constraint("invite_kind_shape", "invite")
    op.alter_column("invite", "role", nullable=False, server_default="player")
    op.alter_column("invite", "campaign_id", nullable=False)
    op.drop_column("invite", "kind")
    _KIND.drop(op.get_bind())

    for old, new in _POLICIES:
        op.execute(f"ALTER POLICY {new} ON invite RENAME TO {old}")
    for old, new in _RENAMED_CONSTRAINTS:
        op.execute(f"ALTER TABLE invite RENAME CONSTRAINT {new} TO {old}")
    for old, new in _RENAMED:
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")
    # The enum keeps `author` and `orga`: Postgres cannot remove a value.
    op.execute("ALTER TYPE invite_role RENAME TO campaign_invite_role")
    op.rename_table("invite", "campaign_invite")
