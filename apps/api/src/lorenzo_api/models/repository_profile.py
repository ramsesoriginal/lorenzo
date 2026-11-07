from __future__ import annotations

import uuid
from datetime import datetime
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

    `visibility` is `private`, `protected` or `public` and `preview` is `off`, `showcase` or
    `public` (RFC 0038 §5); the profile route refuses a flip of the first (it has its own routes,
    ADR 0289 and ADR 0434) and those refuse it while PUBLIC_REPOSITORIES_ENABLED is off (ADR 0290),
    the database does not. `credits` is a list of `{name, role, url}`.
    `cover_picture_id` is a row of the same blob table the other profile pictures use
    (ADR 0056), deleted with the cover.
    """

    __tablename__ = "repository_profile"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('private', 'protected', 'public')",
            name="repository_profile_visibility",
        ),
        CheckConstraint("listed OR visibility = 'public'", name="repository_profile_listed"),
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
    # Whether Discover lists the repository while it is public (ADR 0432, RFC 0051 H2): an Owner of
    # a public repository may turn it off, and the flips turn it back on when the repository stops
    # being public (the check ties the two). An unlisted repository is public and copyable by its
    # address in every other way.
    listed: Mapped[bool] = mapped_column(server_default=text("true"))
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
    # What a listing shows of the current release (ADR 0292): written when a release is published
    # or made current, so that Discover never opens a document.
    release_label: Mapped[str | None]
    released_at: Mapped[datetime | None]
    entry_count: Mapped[int | None]
    stat_definition_count: Mapped[int | None]
    # A's terms (ADR 0431, RFC 0051): whether a repository built on this one may include it. Null
    # is the default for the repository's visibility (`repository_terms.may_be_included`); a
    # value the Owner chose wins.
    may_be_included: Mapped[bool | None]
    # A second term (ADR 0434): whether a repository built on this one may show it, that is, keep it
    # a separate repository its libraries read and see. Null is the default for the visibility;
    # only a protected repository can say no (`repository_terms`).
    may_be_shown: Mapped[bool | None]
    # How the current public release carries each repository it is built on, as the release
    # recorded it: a list of `{id, name, inclusion, licence_label, licence_url}`. Null until the
    # repository makes a public release; written with the listing facts above, so it is always
    # that of the current release. The storefront names what is included from it, and the
    # breaking-change rule compares the choices now with it.
    release_sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    updated_by: Mapped[UpdatedBy]
    updated_at: Mapped[UpdatedAt]
