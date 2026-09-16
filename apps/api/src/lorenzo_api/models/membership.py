from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, CreatedBy, UpdatedAt, UpdatedBy

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
    # ADR 0029/0036: who invited this member (created_by) and who last
    # changed their role (updated_by) - the granter, never the grantee, the
    # same "who made this happen, not who it happened to" distinction ADR
    # 0034 draws for campaign_gm's own created_by.
    created_by: Mapped[CreatedBy]
    updated_by: Mapped[UpdatedBy]

    tenant: Mapped[Tenant] = relationship(lazy="raise_on_sql", back_populates="memberships")
    # foreign_keys explicit: membership gained created_by/updated_by (ADR
    # 0036), a second and third FK to app_user alongside user_id, which this
    # relationship must be pointed at explicitly rather than left for
    # SQLAlchemy to guess between - same shape as User.campaign_gms/
    # tenant_admin_campaign_opt_outs' own existing disambiguation.
    user: Mapped[User] = relationship(
        lazy="raise_on_sql", foreign_keys=[user_id], back_populates="memberships"
    )
