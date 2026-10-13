from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ARRAY, CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, UpdatedAt, UpdatedBy


class RepositoryProfile(Base):
    """What a repository says about itself - ADR 0213, RFC 0038 §1 and §2. One row for each
    repository tenant, `tenant_id` its primary key, made with the repository (and for the
    ones that existed, by the migration; a row missing for any other reason is made when
    the profile is first asked for). Not content: a copy never carries it, and a trigger
    refuses a row for a play tenant. The tenants granted the repository read it through
    the gated read (ADR 0118), so it carries `repository_read` beside `tenant_isolation`.

    `visibility` is `private` or `public` and `preview` is `off`, `showcase` or `public`
    (RFC 0038 §5); the API refuses `public` for the first until the gates that come before
    it are built, the database does not. `credits` is a list of `{name, role, url}`.
    `cover_picture_id` is a row of the same blob table the other profile pictures use
    (ADR 0056), deleted with the cover.
    """

    __tablename__ = "repository_profile"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('private', 'public')", name="repository_profile_visibility"
        ),
        CheckConstraint(
            "preview IN ('off', 'showcase', 'public')", name="repository_profile_preview"
        ),
        CheckConstraint("char_length(summary) <= 280", name="repository_profile_summary"),
        CheckConstraint(
            "licence_label IS NULL OR char_length(licence_label) BETWEEN 1 AND 80",
            name="repository_profile_licence_label",
        ),
        CheckConstraint(
            "licence_url IS NULL OR (licence_label IS NOT NULL AND licence_url ~ '^https://')",
            name="repository_profile_licence_url",
        ),
        CheckConstraint("cardinality(tags) <= 12", name="repository_profile_tags"),
        CheckConstraint("cardinality(languages) <= 8", name="repository_profile_languages"),
        CheckConstraint("jsonb_array_length(credits) <= 20", name="repository_profile_credits"),
    )

    # The primary key leads with tenant_id, so it needs no index of its own.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True
    )
    visibility: Mapped[str] = mapped_column(server_default=text("'private'"))
    preview: Mapped[str] = mapped_column(server_default=text("'showcase'"))
    summary: Mapped[str] = mapped_column(server_default=text("''"))
    licence_label: Mapped[str | None]
    licence_url: Mapped[str | None]
    credits: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    system: Mapped[str | None]
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    cover_picture_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profile_picture.id", ondelete="SET NULL"), unique=True
    )
    updated_by: Mapped[UpdatedBy]
    updated_at: Mapped[UpdatedAt]
