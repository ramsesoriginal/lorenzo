"""Entity slugs over REST (ADR 0107): set/clear, by-slug, and batch resolve."""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_character, make_plain_participant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Entity, EntityPrototype, EntitySlug, Item, ItemInstance, Tenant


async def _make_entity(tenant_id: uuid.UUID, name: str, slug: str | None = None) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        if slug is not None:
            session.add(EntitySlug(entity_id=entity.id, tenant_id=tenant_id, slug=slug))
        await session.commit()
        return entity.id


async def test_set_slug_then_find_the_entity_by_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_entity(tenant_id, "Ashfang")

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/slug", json={"slug": "ashfang"}
    )
    assert response.status_code == 200
    assert response.json() == {"entity_id": str(entity_id), "slug": "ashfang"}

    by_slug = await client.get(f"/tenants/{tenant_id}/entities/by-slug/ashfang")
    assert by_slug.status_code == 200
    assert by_slug.json()["id"] == str(entity_id)
    assert by_slug.json()["slug"] == "ashfang"
    detail = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert detail.json()["slug"] == "ashfang"
    await delete_tenant(tenant_id)


async def test_replacing_a_slug_frees_the_old_one(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    first = await _make_entity(tenant_id, "Ashfang", slug="ashfang")
    second = await _make_entity(tenant_id, "Another sword")

    renamed = await client.put(
        f"/tenants/{tenant_id}/entities/{first}/slug", json={"slug": "ashfang-the-first"}
    )
    assert renamed.status_code == 200
    old = await client.get(f"/tenants/{tenant_id}/entities/by-slug/ashfang")
    assert old.status_code == 404
    assert old.json()["type"] == "entity-slug-not-found"
    taken_over = await client.put(
        f"/tenants/{tenant_id}/entities/{second}/slug", json={"slug": "ashfang"}
    )
    assert taken_over.status_code == 200
    await delete_tenant(tenant_id)


async def test_a_slug_held_by_another_entity_is_a_conflict(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    holder = await _make_entity(tenant_id, "Ashfang", slug="ashfang")
    other = await _make_entity(tenant_id, "Imposter")

    conflict = await client.put(
        f"/tenants/{tenant_id}/entities/{other}/slug", json={"slug": "ashfang"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["type"] == "entity-slug-conflict"
    again = await client.put(
        f"/tenants/{tenant_id}/entities/{holder}/slug", json={"slug": "ashfang"}
    )
    assert again.status_code == 200
    await delete_tenant(tenant_id)


async def test_a_slug_must_fit_lorenzoscript_s_grammar(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """RFC 0027 §3: whatever a slug is, `[text](slug)` must be able to name it."""
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_entity(tenant_id, "Ashfang")

    for slug in ["has space", "-leading-hyphen", "a" * 101, "ümlaut", "semi;colon", ""]:
        response = await client.put(
            f"/tenants/{tenant_id}/entities/{entity_id}/slug", json={"slug": slug}
        )
        assert response.status_code == 422, slug
    for slug in ["Ashfang", "ashfang_2", "a", "a" * 100]:
        response = await client.put(
            f"/tenants/{tenant_id}/entities/{entity_id}/slug", json={"slug": slug}
        )
        assert response.status_code == 200, slug
    await delete_tenant(tenant_id)


async def test_clearing_a_slug_is_idempotent(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_entity(tenant_id, "Ashfang", slug="ashfang")

    for _ in range(2):
        response = await client.delete(f"/tenants/{tenant_id}/entities/{entity_id}/slug")
        assert response.status_code == 204
    assert (await client.get(f"/tenants/{tenant_id}/entities/by-slug/ashfang")).status_code == 404
    detail = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert detail.json()["slug"] is None
    await delete_tenant(tenant_id)


async def test_setting_a_slug_on_an_unknown_entity_is_not_found(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    response = await client.put(
        f"/tenants/{tenant_id}/entities/{uuid.uuid4()}/slug", json={"slug": "ashfang"}
    )
    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_resolve_returns_existing_slugs_once_each_in_the_order_asked(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """kinds is what lets a client honour a LorenzoScript view hint."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        prototype = Entity(tenant_id=tenant_id, name="Longsword")
        sword = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add_all([prototype, sword])
        await session.flush()
        session.add_all(
            [
                Item(entity_id=prototype.id, tenant_id=tenant_id),
                ItemInstance(entity_id=sword.id, tenant_id=tenant_id),
                EntityPrototype(entity_id=sword.id, prototype_id=prototype.id, tenant_id=tenant_id),
            ]
        )
        oda = await make_character(session, tenant_id=tenant_id, name="Oda")
        goblin = await make_being(session, tenant_id=tenant_id, name="Goblin #17")
        slugs = {
            "longsword": prototype.id,
            "ashfang": sword.id,
            "oda": oda.entity_id,
            "goblin-17": goblin.entity_id,
        }
        for slug, entity_id in slugs.items():
            session.add(EntitySlug(entity_id=entity_id, tenant_id=tenant_id, slug=slug))
        await session.commit()

    response = await client.get(
        f"/tenants/{tenant_id}/entities/resolve",
        params=[("slug", s) for s in ["oda", "nobody", "ashfang", "oda", "goblin-17", "longsword"]],
    )

    expected = [
        ("oda", "Oda", ["being", "character"]),
        ("ashfang", "Ashfang", ["item_instance"]),
        ("goblin-17", "Goblin #17", ["being"]),
        ("longsword", "Longsword", ["item"]),
    ]
    assert response.status_code == 200
    assert response.json() == [
        {"slug": slug, "entity_id": str(slugs[slug]), "name": name, "kinds": kinds}
        for slug, name, kinds in expected
    ]
    await delete_tenant(tenant_id)


async def test_resolve_takes_one_to_a_hundred_slugs(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    url = f"/tenants/{tenant_id}/entities/resolve"

    assert (await client.get(url)).status_code == 422
    too_many = [("slug", f"s{k}") for k in range(101)]
    assert (await client.get(url, params=too_many)).status_code == 422
    enough = [("slug", f"s{k}") for k in range(100)]
    assert (await client.get(url, params=enough)).json() == []
    await delete_tenant(tenant_id)


async def test_slugs_resolve_within_their_own_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    ours = await _make_entity(tenant_a, "Ashfang", slug="ashfang")
    await _make_entity(tenant_b, "Other Ashfang", slug="ashfang")

    resolved = await client.get(f"/tenants/{tenant_a}/entities/resolve", params={"slug": "ashfang"})
    assert [r["entity_id"] for r in resolved.json()] == [str(ours)]
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_a_plain_participant_resolves_but_cannot_set_slugs(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Reading shares GET /entities/{id}'s gate; writing is self-or-managed."""
    tenant_id = await make_tenant(test_user_id)
    await make_plain_participant(tenant_id, test_user_id)
    entity_id = await _make_entity(tenant_id, "Ashfang", slug="ashfang")

    resolved = await client.get(
        f"/tenants/{tenant_id}/entities/resolve", params={"slug": "ashfang"}
    )
    assert [r["entity_id"] for r in resolved.json()] == [str(entity_id)]
    assert (await client.get(f"/tenants/{tenant_id}/entities/by-slug/ashfang")).status_code == 200
    forbidden = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/slug", json={"slug": "mine-now"}
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["type"] == "entity-slug-management-forbidden"
    cleared = await client.delete(f"/tenants/{tenant_id}/entities/{entity_id}/slug")
    assert cleared.status_code == 403
    await delete_tenant(tenant_id)


async def test_a_non_participant_cannot_resolve(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id
    await _make_entity(tenant_id, "Ashfang", slug="ashfang")

    response = await client.get(
        f"/tenants/{tenant_id}/entities/resolve", params={"slug": "ashfang"}
    )
    assert response.status_code == 404
    by_slug = await client.get(f"/tenants/{tenant_id}/entities/by-slug/ashfang")
    assert by_slug.status_code == 404
    await delete_tenant(tenant_id)


async def test_an_item_instance_slug_must_be_free_across_all_entities(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    await _make_entity(tenant_id, "Emberdeep", slug="emberdeep")
    async with admin_session_factory() as session:
        prototype = Entity(tenant_id=tenant_id, name="Longsword")
        session.add(prototype)
        await session.flush()
        session.add(Item(entity_id=prototype.id, tenant_id=tenant_id))
        await session.commit()
        prototype_id = prototype.id
    url = f"/tenants/{tenant_id}/item-instances"

    taken = await client.post(url, json={"prototype_id": str(prototype_id), "slug": "emberdeep"})
    assert taken.status_code == 409
    created = await client.post(url, json={"prototype_id": str(prototype_id), "slug": "ashfang"})
    assert created.status_code == 201
    assert created.json()["slug"] == "ashfang"
    resolved = await client.get(
        f"/tenants/{tenant_id}/entities/resolve", params={"slug": "ashfang"}
    )
    assert resolved.json()[0]["kinds"] == ["item_instance"]
    await delete_tenant(tenant_id)


async def test_item_instance_creation_keeps_its_old_slug_contract(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0107: only the new PUT .../slug enforces RFC 0027's grammar; an
    existing client creating instances with any slug keeps working, and the
    slug still resolves exactly."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        prototype = Entity(tenant_id=tenant_id, name="Longsword")
        session.add(prototype)
        await session.flush()
        session.add(Item(entity_id=prototype.id, tenant_id=tenant_id))
        await session.commit()
        prototype_id = prototype.id

    created = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={"prototype_id": str(prototype_id), "slug": "the old sword"},
    )
    assert created.status_code == 201
    resolved = await client.get(
        f"/tenants/{tenant_id}/entities/resolve", params={"slug": "the old sword"}
    )
    assert [r["entity_id"] for r in resolved.json()] == [created.json()["entity_id"]]
    await delete_tenant(tenant_id)
