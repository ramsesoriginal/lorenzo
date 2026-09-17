from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class TenantProfilePicture(Base):
    """Links a Tenant to its one ProfilePicture - see ADR 0056. RLS'd on
    `tenant_id` (its own primary key here), same `tenant_isolation` policy
    shape every RLS'd table in this schema already uses.
    """

    __tablename__ = "tenant_profile_picture"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True
    )
    profile_picture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile_picture.id", ondelete="CASCADE"), unique=True
    )
