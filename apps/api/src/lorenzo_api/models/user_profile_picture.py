from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class UserProfilePicture(Base):
    """Links a User to their one ProfilePicture - see ADR 0056. No
    `tenant_id`/RLS, matching `app_user`'s own global-identity precedent
    (ADR 0022). No relationships declared - both directions are always
    reached by a plain `session.get`/`session.get_one` on a known id, not
    by ORM navigation, the same lean shape every other narrow join table
    added purely for this feature (`tenant_profile_picture`,
    `campaign_profile_picture`) uses.
    """

    __tablename__ = "user_profile_picture"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    # unique=True, not part of the primary key - this is the "one owner"
    # side of a true 1:1 (see ProfilePicture's own docstring): a picture row
    # is never referenced by more than one link.
    profile_picture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile_picture.id", ondelete="CASCADE"), unique=True
    )
