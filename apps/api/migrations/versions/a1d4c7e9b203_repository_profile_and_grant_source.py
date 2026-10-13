"""the repository profile and the source of a grant (ADR 0213)

repository_profile is one row for each repository tenant: its visibility and preview switch
and what it says about itself (summary, licence, credits, tags, system, languages, cover). A
tenant table with tenant_isolation and, because the libraries a repository is granted to read
its profile, repository_read (ADR 0118); a trigger refuses a row for a play tenant. Every
repository that exists gets a private row with the preview at its default.

repository_subscription gains `source`: `invited` for every grant that exists, which is what
the repository's side may write; a library's own, `public`, comes with the public read.

Revision ID: a1d4c7e9b203
Revises: f9b3d6e8a2c4
Create Date: 2026-10-09 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1d4c7e9b203"
down_revision = "f2b8d4a1c597"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT = "current_setting('app.tenant_id')::uuid"
_CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

_ONLY_REPOSITORIES_FUNCTION = """
CREATE FUNCTION repository_profile_only_for_repository() RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM tenant WHERE id = NEW.tenant_id AND kind = 'repository') THEN
        RAISE EXCEPTION 'only a repository has a profile';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
_ONLY_REPOSITORIES_TRIGGER = """
CREATE TRIGGER repository_profile_only_for_repository_trigger
    BEFORE INSERT ON repository_profile
    FOR EACH ROW EXECUTE FUNCTION repository_profile_only_for_repository();
"""


def upgrade() -> None:
    op.create_table(
        "repository_profile",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("visibility", sa.Text(), server_default=sa.text("'private'"), nullable=False),
        sa.Column("preview", sa.Text(), server_default=sa.text("'showcase'"), nullable=False),
        sa.Column("summary", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("licence_label", sa.Text(), nullable=True),
        sa.Column("licence_url", sa.Text(), nullable=True),
        sa.Column(
            "credits", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "tags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("system", sa.Text(), nullable=True),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("cover_picture_id", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cover_picture_id"], ["profile_picture.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.UniqueConstraint("cover_picture_id"),
        sa.CheckConstraint(
            "visibility IN ('private', 'public')", name="repository_profile_visibility"
        ),
        sa.CheckConstraint(
            "preview IN ('off', 'showcase', 'public')", name="repository_profile_preview"
        ),
        sa.CheckConstraint("char_length(summary) <= 280", name="repository_profile_summary"),
        sa.CheckConstraint(
            "licence_label IS NULL OR char_length(licence_label) BETWEEN 1 AND 80",
            name="repository_profile_licence_label",
        ),
        sa.CheckConstraint(
            "licence_url IS NULL OR (licence_label IS NOT NULL AND licence_url ~ '^https://')",
            name="repository_profile_licence_url",
        ),
        sa.CheckConstraint("cardinality(tags) <= 12", name="repository_profile_tags"),
        sa.CheckConstraint("cardinality(languages) <= 8", name="repository_profile_languages"),
        sa.CheckConstraint("jsonb_array_length(credits) <= 20", name="repository_profile_credits"),
    )
    op.create_index("ix_repository_profile_updated_by", "repository_profile", ["updated_by"])
    op.execute(_ONLY_REPOSITORIES_FUNCTION)
    op.execute(_ONLY_REPOSITORIES_TRIGGER)
    op.execute("ALTER TABLE repository_profile ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE repository_profile FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON repository_profile USING (tenant_id = {_TENANT})"
    )
    op.execute(
        "CREATE POLICY repository_read ON repository_profile FOR SELECT "
        "USING (tenant_id = (SELECT repository_read_tenant_id()))"
    )
    # The repositories there are: private, as every repository is until its Owner says otherwise.
    op.execute(
        "INSERT INTO repository_profile (tenant_id) SELECT id FROM tenant WHERE kind = 'repository'"
    )

    op.add_column(
        "repository_subscription",
        sa.Column("source", sa.Text(), server_default=sa.text("'invited'"), nullable=False),
    )
    op.create_check_constraint(
        "repository_subscription_source",
        "repository_subscription",
        "source IN ('invited', 'public')",
    )
    # The repository's side writes a grant it invited; a library's own comes with the public read.
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(
        "CREATE POLICY repository_subscription_grant ON repository_subscription "
        f"FOR INSERT WITH CHECK (repository_tenant_id = {_CURRENT_TENANT} AND source = 'invited')"
    )


def downgrade() -> None:
    op.execute("DROP POLICY repository_subscription_grant ON repository_subscription")
    op.execute(
        "CREATE POLICY repository_subscription_grant ON repository_subscription "
        f"FOR INSERT WITH CHECK (repository_tenant_id = {_CURRENT_TENANT})"
    )
    op.drop_constraint("repository_subscription_source", "repository_subscription")
    op.drop_column("repository_subscription", "source")
    op.drop_table("repository_profile")
    op.execute("DROP FUNCTION repository_profile_only_for_repository()")
