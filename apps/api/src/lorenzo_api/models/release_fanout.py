from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UuidPk, same_tenant_fk


class ReleaseFanout(Base):
    """One announcement a repository owes the libraries that hold it - ADR 0301, RFC 0038
    section 6. Written in the transaction of what it announces (a release, a rollback to an
    earlier release, the flip to private), so it exists if and only if that does: the libraries
    to tell as they were then (`recipients`, in the order they are told), the words (`title`,
    `body`, so that a later edit changes nothing already on its way) and how far it has got
    (`cursor`: the recipients before it have been told). A drain writes a chunk of notices and
    moves the cursor in one transaction, so a drain that stops anywhere is resumed by the next
    one without telling anybody twice and without missing anybody.

    A tenant table of the repository, because it holds who copied it: `tenant_isolation`, and a
    sweep policy that opens only for the process that finishes announcements, across repositories
    (ADR 0092's pattern). Never read by an API route and never copied: not content.
    """

    __tablename__ = "release_fanout"
    __table_args__ = (
        # A release is gone only with its repository; the rollback and the flip to private
        # announce no new release, so there it is null.
        same_tenant_fk(
            "release_fanout_release_id_fkey",
            ["release_id"],
            "repository_release",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "cursor >= 0 AND cursor <= cardinality(recipients)", name="release_fanout_cursor"
        ),
        # Finished means every recipient has been told.
        CheckConstraint(
            "done_at IS NULL OR cursor = cardinality(recipients)", name="release_fanout_done"
        ),
        # The sweep's one question, "is anything left to tell?", reads only what is pending.
        Index(
            "ix_release_fanout_pending",
            "created_at",
            "id",
            postgresql_where=text("done_at IS NULL"),
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    release_id: Mapped[uuid.UUID | None]
    # The notification's type, as `notify_tenant_admins` takes it.
    type: Mapped[str]
    title: Mapped[str]
    body: Mapped[str]
    # Who the notices say made them: the author of the release.
    created_by: Mapped[CreatedBy]
    recipients: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    cursor: Mapped[int] = mapped_column(server_default="0")
    created_at: Mapped[CreatedAt]
    # The last chunk written, and when the last one finished it.
    updated_at: Mapped[datetime | None]
    done_at: Mapped[datetime | None]
