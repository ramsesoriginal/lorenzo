"""What an Author does through the routes that make, change and delete any entry (RFC 0041, ADR
0215 to 0217) under the Author role of ADR 0219: a repository's every entry, a library's catalog
items and nothing more; deleting what other entries inherit from stays with an administrator.
"""

from __future__ import annotations

import uuid

from _author_world import make_item, make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient


async def test_an_author_of_a_repository_makes_changes_and_deletes_any_entry(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="repository", name="Faerûn")
    try:
        author, tenant_id = world.author, world.tenant_id
        t = f"/tenants/{tenant_id}"
        made = await author.post(f"{t}/entities", json={"name": "Elminster", "kinds": ["being"]})
        assert made.status_code == 201, made.text
        entry = made.json()["entity_id"] if "entity_id" in made.json() else made.json()["id"]
        parent = await author.post(f"{t}/entities", json={"name": "Wizard", "kinds": []})
        assert parent.status_code == 201, parent.text
        parent_id = parent.json().get("entity_id") or parent.json()["id"]

        assert (await author.put(f"{t}/entities/{entry}/kinds/item")).status_code in (200, 201)
        assert (await author.delete(f"{t}/entities/{entry}/kinds/item")).status_code == 200
        parents = await author.put(
            f"{t}/entities/{entry}/parents", json={"parent_ids": [parent_id]}
        )
        assert parents.status_code == 200, parents.text

        # What others inherit from is an administrator's to delete.
        refused = await author.delete(f"{t}/entities/{parent_id}")
        assert refused.status_code == 403, refused.text
        assert (await author.delete(f"{t}/entities/{entry}")).status_code == 204
        assert (await author.delete(f"{t}/entities/{parent_id}")).status_code == 204
    finally:
        await world.clean_up()


async def test_an_author_of_a_library_makes_and_changes_items_and_not_beings(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        author, owner, tenant_id = world.author, world.owner, world.tenant_id
        t = f"/tenants/{tenant_id}"
        item = await author.post(f"{t}/entities", json={"name": "Torch", "kinds": ["item"]})
        assert item.status_code == 201, item.text
        item_id = item.json().get("entity_id") or item.json()["id"]

        being = await author.post(f"{t}/entities", json={"name": "Orc", "kinds": ["being"]})
        assert being.status_code == 403, being.text
        bare = await author.post(f"{t}/entities", json={"name": "Thing", "kinds": []})
        assert bare.status_code == 403, bare.text

        # An item takes no being kind from an Author, and an entry that is a being is out of reach.
        assert (await author.put(f"{t}/entities/{item_id}/kinds/being")).status_code == 403
        made = await owner.post(f"{t}/entities", json={"name": "Goblin", "kinds": ["being"]})
        assert made.status_code == 201, made.text
        being_id = made.json().get("entity_id") or made.json()["id"]
        assert (await author.delete(f"{t}/entities/{being_id}")).status_code == 403
        assert (
            await author.put(f"{t}/entities/{being_id}/parents", json={"parent_ids": []})
        ).status_code == 403
        assert (await author.delete(f"{t}/entities/{being_id}/kinds/being")).status_code == 403

        # The Organizer is not held back by any of it.
        assert (await world.orga.delete(f"{t}/entities/{being_id}")).status_code == 204
        # An item nobody inherits from, the Author deletes.
        assert (await author.delete(f"{t}/entities/{item_id}")).status_code == 204
    finally:
        await world.clean_up()


async def test_an_author_cannot_delete_an_item_others_inherit_from_through_the_entry_route(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        author, tenant_id = world.author, world.tenant_id
        t = f"/tenants/{tenant_id}"
        base = await make_item(world.owner, tenant_id, "Weapon")
        child = await make_item(world.owner, tenant_id, "Sword")
        linked = await world.owner.put(
            f"{t}/items/{child}/prototypes", json={"prototype_ids": [str(base)]}
        )
        assert linked.status_code == 200, linked.text
        assert (await author.delete(f"{t}/entities/{base}")).status_code == 403
        assert (await author.delete(f"{t}/entities/{uuid.uuid4()}")).status_code == 404
    finally:
        await world.clean_up()
