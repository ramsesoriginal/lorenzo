"""Libraries that hold a repository, for the announcement tests (ADR 0301): each with an Owner, an
Organizer and an Author, written straight in the database."""

import uuid
from dataclasses import dataclass, field

from _admin_db import admin_session_factory
from sqlalchemy import func, select, text

from lorenzo_api.models import (
    Membership,
    MembershipRole,
    Notification,
    RepositorySubscription,
    Tenant,
    User,
)


@dataclass
class Library:
    id: uuid.UUID
    owner: uuid.UUID
    orga: uuid.UUID
    author: uuid.UUID

    @property
    def told(self) -> list[uuid.UUID]:
        """The people an announcement to the library reaches: not its Author."""
        return [self.owner, self.orga]


@dataclass
class Libraries:
    items: list[Library] = field(default_factory=list)

    @property
    def ids(self) -> list[uuid.UUID]:
        return [library.id for library in self.items]

    @property
    def people(self) -> list[uuid.UUID]:
        return [user for library in self.items for user in library.told]

    @property
    def authors(self) -> list[uuid.UUID]:
        return [library.author for library in self.items]

    async def done(self) -> None:
        async with admin_session_factory() as session:
            for library in self.items:
                tenant = await session.get(Tenant, library.id)
                if tenant is not None:
                    await session.delete(tenant)
            await session.commit()
            for library in self.items:
                for user_id in (library.owner, library.orga, library.author):
                    user = await session.get(User, user_id)
                    if user is not None:
                        await session.delete(user)
            await session.commit()


async def add_libraries(repository: uuid.UUID, count: int, *, source: str = "invited") -> Libraries:
    """`count` libraries holding `repository`, by an invitation or (`source="public"`) by copying
    it."""
    libraries = Libraries()
    async with admin_session_factory() as session:
        for number in range(count):
            library = Tenant(name=f"Library {number}")
            users = [User(authgear_subject_id=f"fanout|{uuid.uuid4()}") for _ in range(3)]
            session.add_all([library, *users])
            await session.flush()
            session.add_all(
                [
                    Membership(
                        tenant_id=library.id, user_id=users[0].id, role=MembershipRole.OWNER
                    ),
                    Membership(tenant_id=library.id, user_id=users[1].id, role=MembershipRole.ORGA),
                    Membership(
                        tenant_id=library.id, user_id=users[2].id, role=MembershipRole.AUTHOR
                    ),
                ]
            )
            await session.flush()
            session.add(
                RepositorySubscription(
                    repository_tenant_id=repository,
                    subscriber_tenant_id=library.id,
                    source=source,
                )
            )
            libraries.items.append(Library(library.id, users[0].id, users[1].id, users[2].id))
        await session.commit()
    return libraries


async def notices_of(users: list[uuid.UUID], type: str | None = None) -> dict[uuid.UUID, int]:
    """How many notices each of these people has, of one type if given."""
    async with admin_session_factory() as session:
        stmt = (
            select(Notification.user_id, func.count())
            .where(Notification.user_id.in_(users))
            .group_by(Notification.user_id)
        )
        if type is not None:
            stmt = stmt.where(Notification.type == type)
        found = dict((await session.execute(stmt)).tuples().all())
    return {user: found.get(user, 0) for user in users}


async def fanouts_of(repository: uuid.UUID) -> list[tuple[int, int, bool, str]]:
    """The repository's announcements, oldest first, as (recipients, cursor, finished, type)."""
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT cardinality(recipients), cursor, done_at IS NOT NULL, type "
                    "FROM release_fanout WHERE tenant_id = :t ORDER BY created_at, id"
                ),
                {"t": repository},
            )
        ).all()
    return [(r[0], r[1], r[2], r[3]) for r in rows]
