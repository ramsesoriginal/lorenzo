from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, UuidPk


class PersonalAccessToken(Base):
    """A user's own API credential (ADR 0268). Only the SHA-256 of the secret is stored: the
    secret is 256 random bits, so a fast hash is enough and the lookup is by hash (an indexed
    equality, nothing to compare in time). `token_hint` is the last four characters, so the list
    can tell two tokens of one name apart. User-level, no tenant and no RLS (see the migration).
    """

    __tablename__ = "personal_access_token"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    token_hash: Mapped[str] = mapped_column(unique=True)
    token_hint: Mapped[str]
    created_at: Mapped[CreatedAt]
    last_used_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class DeviceAuthorization(Base):
    """A device-code approval in progress (ADR 0268, RFC 8628 shape). Holds hashes and the
    approver's choices, never a secret: the token is minted by the first poll that finds the row
    approved, and the row is deleted in the same transaction.
    """

    __tablename__ = "device_authorization"

    id: Mapped[UuidPk]
    device_code_hash: Mapped[str] = mapped_column(unique=True)
    user_code: Mapped[str] = mapped_column(unique=True)
    client_name: Mapped[str | None]
    status: Mapped[str] = mapped_column(server_default="pending")
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    token_name: Mapped[str | None]
    token_expires_at: Mapped[datetime | None]
    expires_at: Mapped[datetime]
    last_polled_at: Mapped[datetime | None]
    created_at: Mapped[CreatedAt]
