from __future__ import annotations

from sqlalchemy.orm import Mapped

from lorenzo_api.db import Base, CreatedAt, UpdatedAt, UuidPk


class ProfilePicture(Base):
    """The actual bytes behind a user/tenant/campaign profile picture - see
    ADR 0056. No `tenant_id`, no RLS: a row here can belong to a `User`
    (global, no tenant) or a `Tenant`/`Campaign` (tenant-scoped), and there
    is no single RLS predicate that correctly covers both - the same reason
    `app_user` itself carries no RLS (ADR 0022). Real tenant isolation lives
    on whichever link table (`user_profile_picture`/`tenant_profile_picture`/
    `campaign_profile_picture`) actually references this row.

    No relationships back to those link tables - nothing navigates from a
    picture to its owner, only the other way (owner id -> link -> this row
    by id), so there's nothing for a relationship here to usefully serve.
    """

    __tablename__ = "profile_picture"

    id: Mapped[UuidPk]
    data: Mapped[bytes]
    file_type: Mapped[str]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
