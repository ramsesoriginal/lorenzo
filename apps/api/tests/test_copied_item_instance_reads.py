"""ADR 0443: why an item instance copied from a repository is in the entity read and in the
database and not in `GET /item-instances` for a library's plain Owner.

It is not a defect of the copy. The copy carries the ownership of the instance (the seeded
repository's Blade is owned by the entry Harpers), and ADR 0040 narrows the instance reads to
whoever can reach the owner: the caller's own characters, a GM's reach, or an ORGA. A plain Owner
reaches none of those, so an owned instance is neither listed nor found by id for them, while an
ownerless one is, and so is any instance for an ORGA. The slice records this and changes nothing.
"""

import uuid

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _hidden_world import names_of
from _repository_actors import Actor, cleanup, make_actor
from _repository_fixtures import seed_every_content_table
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from lorenzo_api.config import get_settings
from lorenzo_api.models import ItemInstance, Membership, MembershipRole, Ownership


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def _copied(
    raw_client: AsyncClient, jwks: FakeJwksServer
) -> tuple[Actor, uuid.UUID, uuid.UUID, dict[str, uuid.UUID]]:
    """The author's repository with a row in every content table, and a library of theirs that
    copied it: the repository, the library and what the library holds, by name."""
    author = await make_actor(raw_client, jwks, "author")
    repository = await author.create_tenant("Fixtures", kind="repository")
    async with admin_session_factory() as session:
        await seed_every_content_table(session, repository)
        await session.commit()
    library = await author.create_tenant("Library")
    shared = await author.put(f"/tenants/{repository}/subscribers/{library}")
    assert shared.status_code in (200, 201), shared.text
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
    copied = await author.post(f"/tenants/{library}/repositories/{repository}/copy", json={})
    assert copied.status_code == 201, copied.text
    return author, repository, library, await names_of(library)


async def _reads(author: Actor, library: uuid.UUID, blade: uuid.UUID) -> tuple[bool, int]:
    """Whether the list has the instance, and what a read of it by id answers."""
    listed = await author.get(f"/tenants/{library}/item-instances", params={"size": 100})
    assert listed.status_code == 200, listed.text
    by_id = await author.get(f"/tenants/{library}/item-instances/{blade}")
    return str(blade) in [i["entity_id"] for i in listed.json()["items"]], by_id.status_code


async def test_a_copied_owned_instance_is_read_by_whoever_reaches_its_owner_as_adr_0040_says(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author, repository, library, ids = await _copied(raw_client, fake_jwks_server)
    try:
        blade = ids["Blade"]

        # It is there: a row of the library, owned by the copy of Harpers, in the entity read.
        async with admin_session_factory() as session:
            assert await session.get(ItemInstance, blade) is not None
            assert (
                await session.scalar(
                    select(Ownership.owner_character_id).where(Ownership.owned_entity_id == blade)
                )
                == ids["Harpers"]
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ItemInstance)
                    .where(ItemInstance.tenant_id == library)
                )
                == 1
            )
        assert (await author.get(f"/tenants/{library}/entities/{blade}")).status_code == 200

        # A plain Owner reaches no owner: owned, so neither listed nor found (ADR 0040).
        assert await _reads(author, library, blade) == (False, 404)

        # Without the owner it is loose loot, which any participant reads.
        async with admin_session_factory() as session:
            await session.execute(delete(Ownership).where(Ownership.owned_entity_id == blade))
            await session.commit()
        assert await _reads(author, library, blade) == (True, 200)
    finally:
        await cleanup([repository, library], [author])


async def test_an_orga_of_the_library_lists_and_finds_the_copied_owned_instance(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author, repository, library, ids = await _copied(raw_client, fake_jwks_server)
    try:
        async with admin_session_factory() as session:
            membership = await session.get_one(Membership, (library, author.user_id))
            membership.role = MembershipRole.ORGA
            await session.commit()

        assert await _reads(author, library, ids["Blade"]) == (True, 200)
    finally:
        await cleanup([repository, library], [author])
