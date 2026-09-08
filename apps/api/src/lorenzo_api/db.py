import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, mapped_column

from lorenzo_api.config import get_settings


class Base(DeclarativeBase):
    # Postgres treats unbounded VARCHAR and TEXT identically - TEXT is the
    # more idiomatic default here. Plain `datetime` otherwise maps to a
    # timezone-naive TIMESTAMP; every timestamp in this schema is TIMESTAMPTZ.
    type_annotation_map = {
        str: Text,
        datetime: DateTime(timezone=True),
    }


# Reusable Annotated column shapes for the three patterns repeated across
# nearly every table - see ADR 0018. Plain Mapped[str]/Mapped[datetime]
# already get TEXT/TIMESTAMPTZ from the type map above; these three cover
# the parts that still need mapped_column() (primary_key, ForeignKey,
# server defaults) - each mapped_column() is copied per class that uses it,
# not shared, which is the documented purpose of this pattern.
UuidPk = Annotated[
    uuid.UUID, mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
]
TenantFk = Annotated[
    uuid.UUID, mapped_column(ForeignKey("tenant.id", ondelete="CASCADE"), index=True)
]
CreatedAt = Annotated[datetime, mapped_column(server_default=text("now()"))]
UpdatedAt = Annotated[datetime, mapped_column(server_default=text("now()"), onupdate=text("now()"))]


engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
