from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, UpdatedAt

if TYPE_CHECKING:
    from lorenzo_api.models.tenant import Tenant
    from lorenzo_api.models.user import User


class MembershipRole(enum.Enum):
    """Tenant-wide administrative access levels - see ADR 0010/0022.
    Campaign-scoped GM/player access is a separate, campaign-level concept
    (RFC 0002), not a value here - a user can validly have no Membership
    row at all and still access campaigns as an ordinary player.
    """

    OWNER = "owner"
    ORGA = "orga"


class Membership(Base):
    """Joins User to Tenant with a tenant-wide administrative access level.
    See ADR 0022 for why `tenant_id` leads the composite primary key.
    """

    __tablename__ = "membership"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        Enum(
            MembershipRole,
            name="membership_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    tenant: Mapped[Tenant] = relationship(lazy="raise_on_sql", back_populates="memberships")
    user: Mapped[User] = relationship(lazy="raise_on_sql", back_populates="memberships")
