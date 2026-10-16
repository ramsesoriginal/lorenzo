"""Facts are ordinary information anchors with a separate existence/name gate (ADR 0305)."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import delete

from lorenzo_api.models import (
    Entity,
    EntityAudience,
    EntityKnowledge,
    Knowledge,
    Membership,
    Player,
)


async def make_fact(client: AsyncClient, tenant: uuid.UUID, name: str = "The lich's bond") -> str:
    response = await client.post(
        f"/tenants/{tenant}/entities", json={"name": name, "slug": "lich-bond", "kinds": ["fact"]}
    )
    assert response.status_code == 201, response.text
    assert response.json()["kinds"] == ["fact"]
    return response.json()["id"]


async def reader_seat(tenant: uuid.UUID, user: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant)
        seat = Player(tenant_id=tenant, campaign_id=campaign.id, user_id=user)
        session.add(seat)
        await session.commit()
        return seat.id


@pytest.mark.parametrize(
    ("outer", "inner"), [(False, False), (False, True), (True, False), (True, True)]
)
async def test_both_audiences_are_explicit_gates(
    client: AsyncClient, test_user_id: uuid.UUID, outer: bool, inner: bool
) -> None:
    tenant = await make_tenant(test_user_id)
    try:
        fact = await make_fact(client, tenant)
        base = f"/tenants/{tenant}/entities/{fact}"
        created = await client.post(
            base + "/information",
            json={
                "title": "The oath",
                "type": "note",
                "is_public": inner,
                "content": "The weapon holds his soul.",
            },
        )
        assert created.status_code == 201, created.text
        note = created.json()["id"]
        seat = await reader_seat(tenant, test_user_id)
        async with admin_session_factory() as session:
            audience = await session.get_one(EntityAudience, uuid.UUID(fact))
            audience.is_public = outer
            await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
            await session.commit()
        detail = await client.get(base)
        assert detail.status_code == (200 if outer else 404), detail.text
        information = await client.get(f"/tenants/{tenant}/information/{note}")
        assert information.status_code == (200 if outer and inner else 404), information.text
        listing = await client.get(
            f"/tenants/{tenant}/entities", params={"kind": "fact", "size": 1}
        )
        assert listing.status_code == 200, listing.text
        assert listing.json()["total"] == int(outer)
        resolved = await client.get(
            f"/tenants/{tenant}/entities/resolve", params={"slug": "lich-bond"}
        )
        assert len(resolved.json()) == int(outer)
        # Sharing an inner row must not share the entry. Then sharing only the entry must
        # not silently grant the note; the two grants are deliberately independent.
        async with admin_session_factory() as session:
            session.add(
                Knowledge(tenant_id=tenant, information_id=uuid.UUID(note), knower_player_id=seat)
            )
            await session.commit()
        assert (await client.get(f"/tenants/{tenant}/information/{note}")).status_code == (
            200 if outer else 404
        )
        async with admin_session_factory() as session:
            session.add(
                EntityKnowledge(tenant_id=tenant, entity_id=uuid.UUID(fact), knower_player_id=seat)
            )
            await session.commit()
        assert (await client.get(base)).status_code == 200
        assert (await client.get(f"/tenants/{tenant}/information/{note}")).status_code == 200
    finally:
        await delete_tenant(tenant)


async def test_fact_subjects_are_optional_explicit_and_visibility_filtered(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    try:
        fact = await make_fact(client, tenant)
        base = f"/tenants/{tenant}/entities/{fact}"
        assert (await client.get(base + "/about")).json() == []
        subjects = []
        for name in ("A lich", "A weapon"):
            response = await client.post(f"/tenants/{tenant}/entities", json={"name": name})
            assert response.status_code == 201, response.text
            subjects.append(response.json()["id"])
        for subject in subjects:
            response = await client.put(base + "/about/" + subject)
            assert response.status_code == 204, response.text
            assert (await client.put(base + "/about/" + subject)).status_code == 204
        assert {row["id"] for row in (await client.get(base + "/about")).json()} == set(subjects)
        assert (await client.get(f"/tenants/{tenant}/entities/{subjects[0]}/facts")).json()[
            "total"
        ] == 1
        assert (await client.put(base + "/about/" + str(uuid.uuid4()))).status_code == 404
        await reader_seat(tenant, test_user_id)
        async with admin_session_factory() as session:
            await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
            await session.commit()
        assert (await client.get(f"/tenants/{tenant}/entities/{subjects[0]}/facts")).json()[
            "total"
        ] == 0
        assert (await client.get(base + "/about")).status_code == 404
        assert (await client.get(base.replace(str(tenant), str(other)))).status_code == 404
    finally:
        await delete_tenant(tenant)
        await delete_tenant(other)


async def test_outer_audience_is_atomic_and_does_not_change_information(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    try:
        fact = await make_fact(client, tenant)
        base = f"/tenants/{tenant}/entities/{fact}"
        note = await client.post(
            base + "/information",
            json={"title": "Secret", "type": "note", "is_public": False, "content": "The bond."},
        )
        assert note.status_code == 201, note.text
        before = await client.get(base + "/audience")
        assert before.json() == {"is_public": False, "entity_ids": [], "player_ids": []}
        assert (await client.put(base + "/audience", json={"is_public": True})).status_code == 428
        seat = await reader_seat(tenant, test_user_id)
        outcomes = await asyncio.gather(
            *[
                client.put(
                    base + "/audience", json=body, headers={"If-Match": before.headers["etag"]}
                )
                for body in ({"is_public": True}, {"is_public": False, "player_ids": [str(seat)]})
            ]
        )
        assert sorted(r.status_code for r in outcomes) == [200, 412]
        assert not (
            await client.get(f"/tenants/{tenant}/information/{note.json()['id']}/audience")
        ).json()["is_public"]
        current = await client.get(base + "/audience")
        bad = await client.put(
            base + "/audience",
            json={"is_public": True, "entity_ids": [str(uuid.uuid4())]},
            headers={"If-Match": current.headers["etag"]},
        )
        assert bad.status_code == 422
        assert (await client.get(base + "/audience")).json() == current.json()
    finally:
        await delete_tenant(tenant)


async def test_hidden_fact_is_absent_from_exports_previews_and_ancestry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    try:
        fact = await make_fact(client, tenant)
        base = f"/tenants/{tenant}/entities/{fact}"
        note = await client.post(
            base + "/information",
            json={
                "title": "The secret",
                "type": "description",
                "is_public": True,
                "content": "The weapon holds his soul.",
            },
        )
        assert note.status_code == 201, note.text
        child = await client.post(
            f"/tenants/{tenant}/entities", json={"name": "Visible child", "parents": [fact]}
        )
        assert child.status_code == 201, child.text
        item = await client.post(
            f"/tenants/{tenant}/items", json={"name": "A catalog item", "prototype_ids": [fact]}
        )
        assert item.status_code == 201, item.text
        seat = await reader_seat(tenant, test_user_id)
        async with admin_session_factory() as session:
            await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
            await session.commit()
        preview = await client.get(base + "/preview")
        assert preview.status_code == 404, preview.text
        detail = await client.get(f"/tenants/{tenant}/entities/{child.json()['id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["prototypes"] == []
        listed = await client.get(f"/tenants/{tenant}/entities")
        assert all(fact not in row["parent_ids"] for row in listed.json()["items"])
        exported = await client.get(f"/tenants/{tenant}/entities/export")
        assert exported.status_code == 200, exported.text
        assert fact not in {row["id"] for row in exported.json()["items"]}
        assert all(fact not in row["parent_ids"] for row in exported.json()["items"])
        item_base = f"/tenants/{tenant}/items/{item.json()['entity_id']}"
        visible_item = await client.get(item_base)
        assert visible_item.status_code == 200, visible_item.text
        assert visible_item.json()["descriptions"] == []
        assert visible_item.json()["prototype_ids"] == []
        assert (await client.get(item_base + "/prototypes/ancestry")).json() == []
        # An outer grant changes the export token before considering If-None-Match.
        async with admin_session_factory() as session:
            session.add(
                EntityKnowledge(entity_id=uuid.UUID(fact), tenant_id=tenant, knower_player_id=seat)
            )
            await session.commit()
        refreshed = await client.get(
            f"/tenants/{tenant}/entities/export",
            headers={"If-None-Match": exported.headers["etag"]},
        )
        assert refreshed.status_code == 200, refreshed.text
        assert fact in {row["id"] for row in refreshed.json()["items"]}
    finally:
        await delete_tenant(tenant)


async def test_outer_group_access_tracks_current_membership(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    from conftest import make_character

    from lorenzo_api.models import CharacterPlayer, GroupMember

    tenant = await make_tenant(test_user_id)
    try:
        fact = await make_fact(client, tenant)
        base = f"/tenants/{tenant}/entities/{fact}"
        seat = await reader_seat(tenant, test_user_id)
        async with admin_session_factory() as session:
            character = await make_character(session, tenant_id=tenant, name="Pia")
            group = Entity(tenant_id=tenant, name="Harpers")
            session.add(group)
            await session.flush()
            session.add_all(
                [
                    CharacterPlayer(
                        tenant_id=tenant, character_entity_id=character.entity_id, player_id=seat
                    ),
                    GroupMember(
                        tenant_id=tenant,
                        group_entity_id=group.id,
                        character_entity_id=character.entity_id,
                    ),
                    EntityKnowledge(
                        tenant_id=tenant, entity_id=uuid.UUID(fact), knower_entity_id=group.id
                    ),
                ]
            )
            await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
            await session.commit()
            group_id = group.id
        assert (await client.get(base)).status_code == 200
        async with admin_session_factory() as session:
            await session.execute(
                delete(GroupMember).where(GroupMember.group_entity_id == group_id)
            )
            await session.commit()
        assert (await client.get(base)).status_code == 404
        assert (await client.get(f"/tenants/{tenant}/entities", params={"kind": "fact"})).json()[
            "total"
        ] == 0
    finally:
        await delete_tenant(tenant)
