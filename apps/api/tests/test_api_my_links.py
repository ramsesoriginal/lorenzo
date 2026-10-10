"""`my/` links (ADR 0240): resolving `my/SLUG` against the being a text belongs
to, and the backlinks that follow from it."""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_plain_participant, make_tenant
from httpx import AsyncClient

from lorenzo_api.description_payloads import write_description
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    EntitySlug,
    Information,
    Item,
    ItemInstance,
    Membership,
    MembershipRole,
    Ownership,
    Payload,
)


class World:
    def __init__(self, tenant_id: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self.ids: dict[str, uuid.UUID] = {}

    async def add(
        self,
        key: str,
        *,
        kind: str,
        slug: str | None = None,
        prototype: str | None = None,
        owner: str | None = None,
        container: str | None = None,
    ) -> uuid.UUID:
        async with admin_session_factory() as session:
            if kind == "being":
                entity_id = (
                    await make_being(session, tenant_id=self.tenant_id, name=key)
                ).entity_id
            else:
                entity = Entity(tenant_id=self.tenant_id, name=key)
                session.add(entity)
                await session.flush()
                entity_id = entity.id
                model = Item if kind == "item" else ItemInstance
                session.add(model(entity_id=entity_id, tenant_id=self.tenant_id))
                await session.flush()
            if slug is not None:
                session.add(EntitySlug(entity_id=entity_id, tenant_id=self.tenant_id, slug=slug))
            if prototype is not None:
                session.add(
                    EntityPrototype(
                        entity_id=entity_id,
                        prototype_id=self.ids[prototype],
                        tenant_id=self.tenant_id,
                    )
                )
            if owner is not None:
                session.add(
                    Ownership(
                        owned_entity_id=entity_id,
                        owner_character_id=self.ids[owner],
                        tenant_id=self.tenant_id,
                    )
                )
            if container is not None:
                session.add(
                    Containment(
                        child_entity_id=entity_id,
                        parent_entity_id=self.ids[container],
                        tenant_id=self.tenant_id,
                    )
                )
            await session.commit()
        self.ids[key] = entity_id
        return entity_id

    async def resolve(
        self, client: AsyncClient, *slugs: str, home: str | None = None
    ) -> dict[str, str]:
        params: list[tuple[str, str]] = [("slug", s) for s in slugs]
        if home is not None:
            params.append(("from", str(self.ids[home])))
        response = await client.get(f"/tenants/{self.tenant_id}/entities/resolve", params=params)
        assert response.status_code == 200, response.text
        inverse = {str(v): k for k, v in self.ids.items()}
        return {row["slug"]: inverse[row["entity_id"]] for row in response.json()}

    async def note(self, client: AsyncClient, on: str, content: str) -> None:
        """A note written as the system would store it (an owned thing's notes
        need a campaign GM through the API, which this has no use for)."""
        async with admin_session_factory() as session:
            info = Information(
                tenant_id=self.tenant_id,
                entity_id=self.ids[on],
                title="Note",
                type="note",
                is_public=True,
            )
            session.add(info)
            await session.flush()
            payload = Payload(tenant_id=self.tenant_id, information_id=info.id)
            session.add(payload)
            await write_description(session, payload=payload, content=content, locale="en")
            await session.commit()

    async def mentions(self, client: AsyncClient, of: str) -> list[str]:
        response = await client.get(f"/tenants/{self.tenant_id}/entities/{self.ids[of]}/backlinks")
        assert response.status_code == 200, response.text
        return sorted(row["name"] for row in response.json()["items"])


async def _world(user_id: uuid.UUID) -> World:
    world = World(await make_tenant(user_id))
    # ORGA reads every instance (ADR 0040); a plain owner would not.
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (world.tenant_id, user_id))
        membership.role = MembershipRole.ORGA
        await session.commit()
    await world.add("Longsword", kind="item", slug="longsword")
    await world.add("Whetstone", kind="item", slug="whetstone")
    await world.add("Aldras", kind="being")
    await world.add("Bryn", kind="being")
    await world.add("Cara", kind="being")
    await world.add("Aldras blade", kind="instance", prototype="Longsword", owner="Aldras")
    await world.add("Bryn blade", kind="instance", prototype="Longsword", owner="Bryn")
    await world.add("Aldras stone", kind="instance", prototype="Whetstone", owner="Aldras")
    return world


async def test_my_resolves_to_the_instance_the_beings_text_is_about(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)

    on_aldras = await world.resolve(client, "my/longsword", "longsword", home="Aldras")
    on_bryn = await world.resolve(client, "my/longsword", home="Bryn")

    assert on_aldras == {"my/longsword": "Aldras blade", "longsword": "Longsword"}
    assert on_bryn == {"my/longsword": "Bryn blade"}
    await delete_tenant(world.tenant_id)


async def test_my_works_from_anything_that_belongs_to_the_being(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await world.add("Pack", kind="instance", owner="Aldras")
    await world.add("Pouch", kind="instance", container="Pack")

    from_stone = await world.resolve(client, "my/longsword", home="Aldras stone")
    from_pouch = await world.resolve(client, "my/longsword", home="Pouch")

    assert from_stone == {"my/longsword": "Aldras blade"}
    assert from_pouch == {"my/longsword": "Aldras blade"}
    await delete_tenant(world.tenant_id)


async def test_my_finds_what_is_in_the_beings_pack_too(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await world.add("Pack", kind="instance", owner="Cara")
    await world.add("Cara blade", kind="instance", prototype="Longsword", container="Pack")

    assert await world.resolve(client, "my/longsword", home="Cara") == {
        "my/longsword": "Cara blade"
    }
    await delete_tenant(world.tenant_id)


async def test_my_is_absent_without_a_being_or_an_instance(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await world.add("Loose rock", kind="instance")

    nothing_held = await world.resolve(client, "my/longsword", home="Cara")
    no_being = await world.resolve(client, "my/longsword", home="Loose rock")
    no_home = await world.resolve(client, "my/longsword")
    unknown = await world.resolve(client, "my/nothing", home="Aldras")

    assert (nothing_held, no_being, no_home, unknown) == ({}, {}, {}, {})
    await delete_tenant(world.tenant_id)


async def test_my_picks_the_same_instance_every_time(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await world.add("Aldras second blade", kind="instance", prototype="Longsword", owner="Aldras")
    await world.add("Aldras magic blade", kind="instance", owner="Aldras")
    await world.add("Magic longsword", kind="item", slug="magic-longsword", prototype="Longsword")
    async with admin_session_factory() as session:
        session.add(
            EntityPrototype(
                entity_id=world.ids["Aldras magic blade"],
                prototype_id=world.ids["Magic longsword"],
                tenant_id=world.tenant_id,
            )
        )
        await session.commit()

    picks = {
        await world.resolve(client, "my/longsword", home="Aldras")
        == {"my/longsword": "Aldras blade"}
        for _ in range(3)
    }

    # A direct instance first, then by name: not the derived "magic" one.
    assert picks == {True}
    # And a derived instance is found when it is all there is.
    assert await world.resolve(client, "my/magic-longsword", home="Aldras") == {
        "my/magic-longsword": "Aldras magic blade"
    }
    await delete_tenant(world.tenant_id)


async def test_my_never_shows_an_instance_the_reader_cannot_see(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await make_plain_participant(world.tenant_id, test_user_id)

    assert await world.resolve(client, "my/longsword", home="Aldras") == {}
    await delete_tenant(world.tenant_id)


async def test_a_my_mention_is_a_backlink_of_the_instance_it_means_only(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await world.note(client, "Aldras", "She draws [[my/Longsword]].")
    await world.note(client, "Aldras stone", "Sharpens [[my/longsword]].")
    await world.note(client, "Bryn", "Cleans [[my/Longsword]].")
    await world.note(client, "Cara", "Wants a [[Longsword]] and [[my/Longsword]].")

    assert await world.mentions(client, "Aldras blade") == ["Aldras", "Aldras stone"]
    assert await world.mentions(client, "Bryn blade") == ["Bryn"]
    # The catalog item is mentioned by the plain link only.
    assert await world.mentions(client, "Longsword") == ["Cara"]
    await delete_tenant(world.tenant_id)


async def test_a_my_mention_follows_the_sword_when_it_changes_hands(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await world.note(client, "Aldras", "She draws [[my/Longsword]].")
    async with admin_session_factory() as session:
        link = await session.get_one(Ownership, world.ids["Aldras blade"])
        link.owner_character_id = world.ids["Cara"]
        await session.commit()

    assert await world.mentions(client, "Aldras blade") == []
    # Aldras has no longsword now, and Cara's text says nothing.
    assert await world.resolve(client, "my/longsword", home="Aldras") == {}
    assert await world.resolve(client, "my/longsword", home="Cara") == {
        "my/longsword": "Aldras blade"
    }
    await delete_tenant(world.tenant_id)
