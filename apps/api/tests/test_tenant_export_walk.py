"""The walk docs/operations/exporting-your-tenant.md tells an owner to do
(ADR 0085), run for real against a populated tenant: page through every
documented list endpoint with a deliberately tiny page size, and confirm the
rows that were put in come back out. If a table stops being reachable this
fails - the runbook and this test change together.
"""

import json
import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_player, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import CharacterPlayer, Entity, Item, User


async def _walk(client: AsyncClient, url: str) -> list[dict[str, object]]:
    """Every row of a paginated list: `page`/`size`, following `pages`."""
    items: list[dict[str, object]] = []
    page = 1
    while True:
        response = await client.get(url, params={"page": page, "size": 2})
        assert response.status_code == 200, f"{url}: {response.text}"
        body = response.json()
        items.extend(body["items"])
        if page >= body["pages"]:
            return items
        page += 1


def _contains(rows: list[dict[str, object]], needle: object) -> bool:
    return str(needle) in json.dumps(rows)


async def test_every_documented_read_returns_the_rows_that_went_in(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    base = f"/tenants/{tenant_id}"

    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="The Campaign")
        players = [
            await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
            for _ in range(3)
        ]
        character = await make_character(
            session, tenant_id=tenant_id, name="Alice", owner_player_id=players[0].id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id,
                player_id=players[0].id,
                tenant_id=tenant_id,
            )
        )
        proto = Entity(tenant_id=tenant_id, name="Sword")
        session.add(proto)
        await session.flush()
        session.add(Item(entity_id=proto.id, tenant_id=tenant_id))
        await session.commit()
        campaign_id, character_id, proto_id = campaign.id, character.entity_id, proto.id
        player_ids = [p.id for p in players]
        player_user_ids = [p.user_id for p in players]

    async def post(path: str, body: dict[str, object]) -> dict[str, str]:
        response = await client.post(f"{base}{path}", json=body)
        assert response.status_code == 201, f"{path}: {response.text}"
        return dict(response.json())

    instance = await post("/item-instances", {"prototype_id": str(proto_id)})
    group = await post(
        "/groups", {"name": "The Party", "member_character_ids": [str(character_id)]}
    )
    information = await post(
        f"/entities/{proto_id}/information",
        {"title": "Lore", "type": "lore", "is_public": False, "content": "text", "locale": "en"},
    )
    stat_group = await post("/stat-groups", {"name": "Physical", "priority": 1})
    definition = await post(
        "/stat-definitions",
        {"stat_group_id": stat_group["id"], "name": "weight", "value_type": "int"},
    )
    grant = await client.put(f"{base}/information/{information['id']}/knowers/{character_id}")
    assert grant.status_code == 200

    # Tenant-level tables.
    assert (await client.get(base)).status_code == 200
    assert _contains(await _walk(client, f"{base}/memberships"), test_user_id)
    assert _contains(await _walk(client, f"{base}/campaigns"), campaign_id)
    assert await _walk(client, f"{base}/activity-log")  # every write above logged

    # Campaign-level tables (more than one page of players, on purpose).
    campaign_players = await _walk(client, f"{base}/campaigns/{campaign_id}/players")
    assert all(_contains(campaign_players, pid) for pid in player_ids)
    gms = await client.get(f"{base}/campaigns/{campaign_id}/gms")
    assert gms.status_code == 200
    assert isinstance(gms.json(), list)  # also a plain list, not a page

    # Lists are summaries; the detail reads carry the rest (the runbook says so).
    campaign_detail = await client.get(f"{base}/campaigns/{campaign_id}")
    assert campaign_detail.status_code == 200
    assert "description" in campaign_detail.json()
    character_detail = await client.get(f"{base}/characters/{character_id}")
    assert character_detail.status_code == 200
    assert _contains(character_detail.json()["players"], player_ids[0])

    # The entity/component core.
    assert _contains(await _walk(client, f"{base}/characters"), character_id)
    assert _contains(await _walk(client, f"{base}/beings"), character_id)
    assert _contains(await _walk(client, f"{base}/items"), proto_id)
    assert _contains(await _walk(client, f"{base}/item-instances"), instance["entity_id"])
    entities = await _walk(client, f"{base}/entities")
    assert all(_contains(entities, i) for i in (character_id, proto_id, group["id"]))

    # Groups and their members.
    assert _contains(await _walk(client, f"{base}/groups"), group["id"])
    # Members come back as a plain list, not a page - one of the few reads
    # the runbook has to call out.
    members = await client.get(f"{base}/groups/{group['id']}/members")
    assert members.status_code == 200
    assert isinstance(members.json(), list)
    assert _contains(members.json(), character_id)

    # Information is per-entity (there is no collection endpoint): the entity
    # detail lists what the caller may see. The exporter is a tenant OWNER, who
    # reads GM-only information like an ORGA (ADR 0091).
    detail = await client.get(f"{base}/entities/{proto_id}")
    assert detail.status_code == 200
    assert _contains(detail.json()["information"], information["id"])

    # The two listings ADR 0085 added.
    assert _contains(await _walk(client, f"{base}/knowledge"), information["id"])
    assert _contains(await _walk(client, f"{base}/stat-groups"), stat_group["id"])
    assert _contains(await _walk(client, f"{base}/stat-definitions"), definition["id"])

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        for user_id in player_user_ids:
            await session.delete(await session.get_one(User, user_id))
        await session.commit()
