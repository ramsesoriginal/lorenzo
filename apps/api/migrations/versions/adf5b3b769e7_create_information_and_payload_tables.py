"""create information and payload tables

Revision ID: adf5b3b769e7
Revises: e666b3c5be95
Create Date: 2026-09-08 17:16:30.821030

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "adf5b3b769e7"
down_revision: str | None = "e666b3c5be95"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TENANT_SCOPED_TABLES = (
    "information",
    "payload",
    "payload_description",
    "payload_document",
    "payload_number",
    "payload_picture",
)


def _enable_rls(table: str) -> None:
    # See ADR 0012 for why both ENABLE and FORCE are needed, and ADR 0002 for
    # the currently-unenforced-in-practice caveat (the app's own DB role is a
    # superuser, which bypasses RLS unconditionally, independent of this
    # policy being correct).
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id')::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "information",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entity.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", "type"),
    )
    op.create_index(
        op.f("ix_information_entity_id"), "information", ["entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_information_tenant_id"), "information", ["tenant_id"], unique=False
    )

    op.create_table(
        "payload",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("information_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["information_id"], ["information.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payload_information_id"), "payload", ["information_id"], unique=False)
    op.create_index(op.f("ix_payload_tenant_id"), "payload", ["tenant_id"], unique=False)

    op.create_table(
        "payload_description",
        sa.Column("payload_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["payload_id"], ["payload.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("payload_id"),
    )
    op.create_index(
        op.f("ix_payload_description_tenant_id"),
        "payload_description",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "payload_document",
        sa.Column("payload_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["payload_id"], ["payload.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("payload_id"),
    )
    op.create_index(
        op.f("ix_payload_document_tenant_id"), "payload_document", ["tenant_id"], unique=False
    )

    op.create_table(
        "payload_number",
        sa.Column("payload_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(["payload_id"], ["payload.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("payload_id"),
    )
    op.create_index(
        op.f("ix_payload_number_tenant_id"), "payload_number", ["tenant_id"], unique=False
    )

    op.create_table(
        "payload_picture",
        sa.Column("payload_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["payload_id"], ["payload.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("payload_id"),
    )
    op.create_index(
        op.f("ix_payload_picture_tenant_id"), "payload_picture", ["tenant_id"], unique=False
    )

    for table in _TENANT_SCOPED_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(op.f("ix_payload_picture_tenant_id"), table_name="payload_picture")
    op.drop_table("payload_picture")
    op.drop_index(op.f("ix_payload_number_tenant_id"), table_name="payload_number")
    op.drop_table("payload_number")
    op.drop_index(op.f("ix_payload_document_tenant_id"), table_name="payload_document")
    op.drop_table("payload_document")
    op.drop_index(op.f("ix_payload_description_tenant_id"), table_name="payload_description")
    op.drop_table("payload_description")
    op.drop_index(op.f("ix_payload_tenant_id"), table_name="payload")
    op.drop_index(op.f("ix_payload_information_id"), table_name="payload")
    op.drop_table("payload")
    op.drop_index(op.f("ix_information_tenant_id"), table_name="information")
    op.drop_index(op.f("ix_information_entity_id"), table_name="information")
    op.drop_table("information")
