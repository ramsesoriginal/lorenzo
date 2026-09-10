import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column

from lorenzo_api.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    # Postgres treats unbounded VARCHAR and TEXT identically - TEXT is the
    # more idiomatic default here. Plain `datetime` otherwise maps to a
    # timezone-naive TIMESTAMP; every timestamp in this schema is TIMESTAMPTZ.
    type_annotation_map = {
        str: Text,
        datetime: DateTime(timezone=True),
    }
    # AsyncAttrs: every relationship() is lazy="raise_on_sql" (ADR 0018) -
    # `await obj.awaitable_attrs.some_relationship` is the sanctioned escape
    # hatch for the rare case that genuinely needs an on-demand lazy load
    # instead of an upfront eager-load chain.


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

# Nullable, unlike CreatedAt/UpdatedAt - a timestamp can never become
# unknown, but an attribution can, the moment the attributed user deletes
# their own account (ADR 0029). ON DELETE SET NULL matches every other "the
# referenced actor is gone, the row survives" case already in this schema
# (Being/Character.owner_player_id) - losing your account clears attribution
# on everything you ever touched, it doesn't delete any of it. Declared as
# two separate aliases (rather than one reused twice) to match
# CreatedAt/UpdatedAt's own naming precedent, even though their shapes
# happen to be identical here.
CreatedBy = Annotated[
    uuid.UUID | None, mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
]
UpdatedBy = Annotated[
    uuid.UUID | None, mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
]


# pool_recycle: the deploy target (Neon, ADR 0011) fronts Postgres with its
# own pooler, which can drop an idle backend connection without telling
# this side's pool - recycling proactively avoids handing out one that's
# already gone. pool_pre_ping catches the rest (a connection that died for
# any other reason) with one cheap round-trip before real use.
engine = create_async_engine(get_settings().database_url, pool_pre_ping=True, pool_recycle=1800)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
