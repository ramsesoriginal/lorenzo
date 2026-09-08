import uuid

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class Tenant(Base):
    """Minimal bootstrap - just enough for other tables to reference a real
    tenant. The full model (name, owner, etc.) lands with ADR 0010's actual
    implementation.
    """

    __tablename__ = "tenant"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
