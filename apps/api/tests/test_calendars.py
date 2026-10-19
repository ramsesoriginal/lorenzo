"""Calendar core through the real HTTP API (ADR 0308)."""

import asyncio
import uuid
from copy import deepcopy

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from lorenzo_api.models import Entity, Membership, Player

DEFINITION = {
    "format": "lorenzo.calendar/1",
    "segments": [
        {"key": "first", "name": "First", "days": 27},
        {"key": "festival", "name": "Festival", "days": 2, "kind": "festival", "in_week": False},
    ],
    "week": {"length": 7, "reference": {"year": 0, "segment": "first", "day": 1}, "weekday": 0},
}


async def make_calendar(client, tenant, **fields):
    response = await client.post(
        f"/tenants/{tenant}/calendars",
        json={"name": "Calendar", "definition": DEFINITION, **fields},
    )
    assert response.status_code == 201, response.text
    return response


async def test_preview_is_pure_and_calendar_writes_are_conditional(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        made = await make_calendar(client, tenant)
        base = f"/tenants/{tenant}/calendars/{made.json()['entity_id']}"
        async with admin_session_factory() as session:
            before = await session.scalar(select(func.count()).where(Entity.tenant_id == tenant))
        year = await client.get(base + "/years/-1")
        assert year.status_code == 200, year.text
        assert len(year.json()["segments"][0]["days"]) == 27
        assert year.json()["segments"][1]["days"][0]["weekday"] is None
        async with admin_session_factory() as session:
            assert (
                await session.scalar(select(func.count()).where(Entity.tenant_id == tenant))
                == before
            )
        assert (await client.put(base + "/definition", json=DEFINITION)).status_code == 428
        changed = deepcopy(DEFINITION)
        changed["segments"][0]["name"] = "Renamed"
        updated = await client.put(
            base + "/definition", json=changed, headers={"If-Match": made.headers["etag"]}
        )
        assert updated.status_code == 200, updated.text
        assert updated.headers["etag"] != made.headers["etag"]
        assert (
            await client.put(
                base + "/definition", json=DEFINITION, headers={"If-Match": made.headers["etag"]}
            )
        ).status_code == 412
        entity = await client.get(f"/tenants/{tenant}/entities/{made.json()['entity_id']}")
        assert entity.status_code == 200, entity.text
        assert entity.json()["kinds"] == ["calendar"]
    finally:
        await delete_tenant(tenant)


async def test_hidden_calendar_is_absent_from_reads_and_counts(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        made = await make_calendar(client, tenant, slug="hidden-calendar")
        entity = made.json()["entity_id"]
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(Player(tenant_id=tenant, campaign_id=campaign.id, user_id=test_user_id))
            await session.execute(delete(Membership).where(Membership.tenant_id == tenant))
            await session.commit()
        assert (await client.get(f"/tenants/{tenant}/calendars/{entity}")).status_code == 404
        assert (
            await client.get(f"/tenants/{tenant}/calendars/{entity}/years/0")
        ).status_code == 404
        assert (await client.get(f"/tenants/{tenant}/calendars")).json()["total"] == 0
        assert (await client.get(f"/tenants/{tenant}/entities")).json()[
            "total"
        ] == 1  # only campaign entry
        assert (
            await client.get(
                f"/tenants/{tenant}/entities/resolve", params={"slug": "hidden-calendar"}
            )
        ).json() == []
    finally:
        await delete_tenant(tenant)


async def test_calendar_isolation_and_concurrent_definition_edits(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    try:
        made = await make_calendar(client, tenant)
        entity = made.json()["entity_id"]
        assert (await client.get(f"/tenants/{other}/calendars/{entity}")).status_code == 404
        left, right = deepcopy(DEFINITION), deepcopy(DEFINITION)
        left["segments"][0]["days"] = 28
        right["segments"][0]["days"] = 29
        base = f"/tenants/{tenant}/calendars/{entity}/definition"
        results = await asyncio.gather(
            *(
                client.put(base, json=d, headers={"If-Match": made.headers["etag"]})
                for d in (left, right)
            )
        )
        assert sorted(r.status_code for r in results) == [200, 412]
    finally:
        await delete_tenant(tenant)
        await delete_tenant(other)


async def test_calendar_audience_is_independent_of_information(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        made = await make_calendar(client, tenant)
        base = f"/tenants/{tenant}/entities/{made.json()['entity_id']}"
        note = await client.post(
            base + "/information",
            json={"title": "Secret", "type": "note", "content": "Private", "is_public": False},
        )
        assert note.status_code == 201, note.text
        gate = await client.get(base + "/audience")
        assert gate.status_code == 200, gate.text
        shared = await client.put(
            base + "/audience", json={"is_public": True}, headers={"If-Match": gate.headers["etag"]}
        )
        assert shared.status_code == 200, shared.text
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(Player(tenant_id=tenant, campaign_id=campaign.id, user_id=test_user_id))
            await session.execute(delete(Membership).where(Membership.tenant_id == tenant))
            await session.commit()
        assert (
            await client.get(f"/tenants/{tenant}/calendars/{made.json()['entity_id']}")
        ).status_code == 200
        assert (
            await client.get(f"/tenants/{tenant}/information/{note.json()['id']}")
        ).status_code == 404
    finally:
        await delete_tenant(tenant)


async def test_calendar_copy_release_and_reviewable_definition_update(raw_client, fake_jwks_server):
    from _repository_actors import cleanup, make_actor

    from lorenzo_api.models import Calendar
    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content

    author = await make_actor(raw_client, fake_jwks_server, "calendar-author")
    keeper = await make_actor(raw_client, fake_jwks_server, "calendar-keeper")
    repository = await author.create_tenant("Calendar repository", kind="repository")
    library = await keeper.create_tenant("Calendar library")
    try:
        made = await author.post(
            f"/tenants/{repository}/calendars", json={"name": "Calendar", "definition": DEFINITION}
        )
        assert made.status_code == 201, made.text
        source = made.json()["entity_id"]
        assert (await author.put(f"/tenants/{repository}/subscribers/{library}")).status_code in (
            200,
            201,
        )
        assert (await author.put(f"/tenants/{repository}/published", json={})).status_code == 200
        copied = await keeper.post(f"/tenants/{library}/repositories/{repository}/copy", json={})
        assert copied.status_code == 201, copied.text
        async with admin_session_factory() as session:
            local = await session.scalar(
                select(Calendar.entity_id).where(Calendar.tenant_id == library)
            )
            content = await load_content(session, repository)
            document, files = encode(content)
            assert decode(document, files).calendars == content.calendars
        local_url = f"/tenants/{library}/calendars/{local}"
        assert (await keeper.get(local_url)).json()["definition"] == made.json()["definition"]
        upstream = deepcopy(DEFINITION)
        upstream["segments"][0]["days"] = 28
        edited = await raw_client.put(
            f"/tenants/{repository}/calendars/{source}/definition",
            json=upstream,
            headers={**author.headers, "If-Match": made.headers["etag"]},
        )
        assert edited.status_code == 200, edited.text
        updates_url = f"/tenants/{library}/repositories/{repository}/updates"
        updates = await keeper.get(updates_url)
        assert updates.status_code == 200, updates.text
        row = next(r for r in updates.json()["changed"] if r["source_id"] == source)
        field = next(f for f in row["fields"] if f["field"] == "calendar_definition")
        assert field["state"] == "clean"
        applied = await keeper.post(
            updates_url,
            json={"actions": [{"kind": "entity", "source_id": source, "action": "apply"}]},
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["not_applied"] == []
        assert (await keeper.get(local_url)).json()["definition"] == edited.json()["definition"]
    finally:
        await cleanup([library, repository], [author, keeper])
