"""Clock coordinates are optional, exact and independent from order (ADR 0320)."""

import uuid

from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_calendars import make_calendar


async def make_clock(client, tenant, **fields):
    response = await client.post(f"/tenants/{tenant}/clocks", json={"name": "Mainland", **fields})
    assert response.status_code == 201, response.text
    return response


async def test_clock_reading_reckoning_and_stale_writes(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        clock = await make_clock(client, tenant, slug="mainland")
        cid = clock.json()["entity_id"]
        entity = await client.get(f"/tenants/{tenant}/entities/{cid}")
        assert entity.json()["kinds"] == ["clock"]
        calendar = await make_calendar(client, tenant)
        cal = calendar.json()["entity_id"]
        base = f"/tenants/{tenant}/clocks/{cid}"
        before = await client.get(base + "/reckonings")
        body = {"date": {"year": 0, "segment": "first", "day": 1}, "reading": "17"}
        assert (await client.put(base + f"/reckonings/{cal}", json=body)).status_code == 428
        saved = await client.put(
            base + f"/reckonings/{cal}", json=body, headers={"If-Match": before.headers["etag"]}
        )
        assert saved.status_code == 200, saved.text
        assert (
            await client.put(
                base + f"/reckonings/{cal}", json=body, headers={"If-Match": before.headers["etag"]}
            )
        ).status_code == 412
        mapped = await client.post(
            base + "/date-reading",
            json={"calendar_entity_id": cal, "date": {"year": 0, "segment": "festival", "day": 1}},
        )
        assert mapped.status_code == 200, mapped.text
        assert mapped.json()["reading"] == {
            "lo": "44",
            "hi": "45",
            "lo_inclusive": True,
            "hi_inclusive": False,
        }
        event = await client.post(
            f"/tenants/{tenant}/entities", json={"name": "Arrival", "kinds": ["event"]}
        )
        eventid = event.json()["id"]
        readings = f"/tenants/{tenant}/events/{eventid}/clock-readings"
        empty = await client.get(readings)
        value = {"reading": {"lo": "1/3", "hi": "2/3"}, "is_shared": True}
        result = await client.put(
            readings + f"/{cid}", json=value, headers={"If-Match": empty.headers["etag"]}
        )
        assert result.status_code == 200, result.text
        assert result.json()["items"][0]["reading"]["lo"] == "1/3"
        assert (
            await client.put(
                base, json={"ticking": False}, headers={"If-Match": clock.headers["etag"]}
            )
        ).status_code == 409
        assert (await client.delete(f"/tenants/{tenant}/entities/{cid}")).status_code == 409
    finally:
        await delete_tenant(tenant)


async def test_timeless_clock_and_invalid_ranges(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    try:
        clock = await make_clock(client, tenant, ticking=False)
        cid = clock.json()["entity_id"]
        event = await client.post(
            f"/tenants/{tenant}/entities", json={"name": "Arrival", "kinds": ["event"]}
        )
        readings = f"/tenants/{tenant}/events/{event.json()['id']}/clock-readings"
        empty = await client.get(readings)
        for reading in [
            {"lo": "1", "hi": "2"},
            {"lo": "2", "hi": "1"},
            {"lo": "0", "hi": "0", "hi_inclusive": False},
        ]:
            result = await client.put(
                readings + f"/{cid}",
                json={"reading": reading},
                headers={"If-Match": empty.headers["etag"]},
            )
            assert result.status_code == 422, result.text
    finally:
        await delete_tenant(tenant)


async def test_reading_visibility_has_no_private_counts_or_revisions(raw_client, fake_jwks_server):
    from test_session_play import event
    from test_story_sessions import world

    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        e = await event(w, "Arrival")
        c = await w.author.post(
            f"/tenants/{t}/clocks", json={"name": "Public clock", "is_public": True}
        )
        assert c.status_code == 201, c.text
        cid = c.json()["entity_id"]
        base = f"/tenants/{t}/events/{e}/clock-readings"
        before = await w.outsider.get(base)
        owner = await w.author.get(base)
        value = {"reading": {"lo": "17", "hi": "17"}}
        saved = await w.author.client.put(
            base + f"/{cid}",
            json=value,
            headers={**w.author.headers, "If-Match": owner.headers["etag"]},
        )
        assert saved.status_code == 200, saved.text
        private = await w.outsider.get(base)
        assert private.json()["items"] == []
        assert private.headers["etag"] == before.headers["etag"]
        denied = await w.outsider.client.put(
            base + f"/{cid}",
            json=value,
            headers={**w.outsider.headers, "If-Match": private.headers["etag"]},
        )
        assert denied.status_code == 403
        shared = await w.author.client.put(
            base + f"/{cid}",
            json={**value, "is_shared": True},
            headers={**w.author.headers, "If-Match": saved.headers["etag"]},
        )
        assert shared.status_code == 200, shared.text
        assert len((await w.outsider.get(base)).json()["items"]) == 1
        gate = f"/tenants/{t}/entities/{cid}/audience"
        current = await w.author.get(gate)
        hidden = await w.author.client.put(
            gate,
            json={"is_public": False, "entity_ids": [], "player_ids": []},
            headers={**w.author.headers, "If-Match": current.headers["etag"]},
        )
        assert hidden.status_code == 200, hidden.text
        invisible = await w.outsider.get(base)
        assert invisible.json()["items"] == []
        assert invisible.headers["etag"] == before.headers["etag"]
        assert (await w.outsider.get(f"/tenants/{t}/clocks")).json() == []
        assert (await w.outsider.get(f"/tenants/{t}/clocks/{cid}")).status_code == 404
        assert (await w.outsider.get(f"/tenants/{t}/clocks/{uuid.uuid4()}")).status_code == 404
    finally:
        await w.clean_up()


async def test_clock_collection_writes_serialize_and_calendar_mapping_is_protected(
    client, test_user_id
):
    import asyncio
    from copy import deepcopy

    from test_calendars import DEFINITION

    t = await make_tenant(test_user_id)
    try:
        c = await make_clock(client, t)
        d = await make_clock(client, t, name="Second")
        e = await client.post(
            f"/tenants/{t}/entities", json={"name": "Departure", "kinds": ["event"]}
        )
        base = f"/tenants/{t}/events/{e.json()['id']}/clock-readings"
        version = (await client.get(base)).headers["etag"]
        results = await asyncio.gather(
            *[
                client.put(
                    base + f"/{clock.json()['entity_id']}",
                    json={"reading": {"lo": "1", "hi": "1"}},
                    headers={"If-Match": version},
                )
                for clock in [c, d]
            ]
        )
        assert sorted(r.status_code for r in results) == [200, 412]
        calendar = await make_calendar(client, t)
        cid, cal = c.json()["entity_id"], calendar.json()["entity_id"]
        url = f"/tenants/{t}/clocks/{cid}/reckonings"
        version = (await client.get(url)).headers["etag"]
        assert (
            await client.put(
                url + f"/{cal}",
                json={"date": {"year": 0, "segment": "first", "day": 1}, "reading": "0"},
                headers={"If-Match": version},
            )
        ).status_code == 200
        definition = deepcopy(DEFINITION)
        definition["segments"][0]["name"] = "Renamed"
        route = f"/tenants/{t}/calendars/{cal}/definition"
        renamed = await client.put(
            route, json=definition, headers={"If-Match": calendar.headers["etag"]}
        )
        assert renamed.status_code == 200, renamed.text
        definition["segments"][0]["days"] = 28
        refused = await client.put(
            route, json=definition, headers={"If-Match": renamed.headers["etag"]}
        )
        assert refused.status_code == 409, refused.text
    finally:
        await delete_tenant(t)


async def test_clock_content_round_trips_copy_release_and_purge(raw_client, fake_jwks_server):
    from _admin_db import admin_session_factory
    from _repository_actors import cleanup
    from _repository_fixtures import seed_every_content_table
    from test_story_sessions import world

    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content

    w, _, _ = await world(raw_client, fake_jwks_server)
    repository = await w.owner.create_tenant("Clock repository", kind="repository")
    try:
        async with admin_session_factory() as db:
            await seed_every_content_table(db, repository)
            await db.commit()
            source = await load_content(db, repository)
            document, files = encode(source)
            restored = decode(document, files)
            assert restored.clocks == source.clocks
            assert restored.clock_readings == source.clock_readings
            assert restored.calendar_reckonings == source.calendar_reckonings
            assert restored.clock_relationships == source.clock_relationships
        assert (
            await w.owner.put(f"/tenants/{repository}/subscribers/{w.tenant_id}")
        ).status_code in [200, 201]
        published = await w.owner.put(f"/tenants/{repository}/published")
        assert published.status_code == 200, published.text
        route = f"/tenants/{w.tenant_id}/repositories/{repository}/copy"
        for body in [{}, {"again": "purge"}]:
            copied = await w.owner.post(route, json=body)
            assert copied.status_code == 201, copied.text
            async with admin_session_factory() as db:
                content = await load_content(db, w.tenant_id)
                assert len(content.clocks) == 2
                assert (
                    len(content.clock_readings)
                    == len(content.calendar_reckonings)
                    == len(content.clock_relationships)
                    == 1
                )
                assert set(content.clocks).isdisjoint(source.clocks)
                # Canonical UUID ordering may reverse during copy. Compare the actual
                # affine relationship in each named direction, rather than raw JSON.
                from fractions import Fraction

                from lorenzo_api.clock_conversion import RelationDefinition

                def oriented_relationships(value):
                    result = {}
                    for (first, second), record in value.clock_relationships.items():
                        definition = RelationDefinition.model_validate(record["data"])
                        if value.entities[first] > value.entities[second]:
                            first, second = second, first
                            definition = definition.inverse()
                        result[(value.entities[first], value.entities[second])] = (
                            Fraction(definition.ratio),
                            definition.clock_anchor,
                            definition.reference_anchor,
                            record["is_shared"],
                        )
                    return result

                assert oriented_relationships(content) == oriented_relationships(source)
                for source_id, clock_id in content.clock_readings:
                    assert source_id in content.entities and clock_id in content.clocks
    finally:
        await cleanup([repository], [])
        await w.clean_up()


async def test_clock_integrity_is_enforced_below_the_api(client, test_user_id):
    import pytest
    from _admin_db import admin_session_factory
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    t = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    try:
        clock = await make_clock(client, t)
        event = await client.post(
            f"/tenants/{t}/entities", json={"name": "Event", "kinds": ["event"]}
        )
        cid, eid = clock.json()["entity_id"], event.json()["id"]
        insert = """INSERT INTO event_clock_reading(event_entity_id,clock_entity_id,tenant_id,data)
          VALUES(:event,:clock,:tenant,CAST(:data AS jsonb))"""
        import json

        for tenant, value in [
            (other, {"lo": "1", "hi": "1", "lo_inclusive": True, "hi_inclusive": True}),
            (t, {"lo": "2", "hi": "1", "lo_inclusive": True, "hi_inclusive": True}),
        ]:
            async with admin_session_factory() as db:
                with pytest.raises(IntegrityError):
                    await db.execute(
                        text(insert),
                        {"event": eid, "clock": cid, "tenant": tenant, "data": json.dumps(value)},
                    )
                    await db.flush()
                await db.rollback()
        base = f"/tenants/{t}/events/{eid}/clock-readings"
        version = (await client.get(base)).headers["etag"]
        assert (
            await client.put(
                base + f"/{cid}",
                json={"reading": {"lo": "1", "hi": "1"}},
                headers={"If-Match": version},
            )
        ).status_code == 200
        async with admin_session_factory() as db:
            with pytest.raises(IntegrityError):
                await db.execute(
                    text("UPDATE clock SET ticking=false WHERE entity_id=:id"), {"id": cid}
                )
                await db.flush()
            await db.rollback()
    finally:
        await delete_tenant(t)
        await delete_tenant(other)


def test_clock_record_changes_affect_release_hashes_and_three_way_review():
    from copy import deepcopy

    from lorenzo_api.repository_content import Content, entity_snapshot, index_entities
    from lorenzo_api.repository_digest import digest_of, live_rows
    from lorenzo_api.repository_updates import diff

    tenant, event, clock = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    content = Content(
        tenant_id=tenant, entities={event: "Arrival", clock: "Mainland"}, clocks={clock: True}
    )
    content.kinds[event] = {"event"}
    content.kinds[clock] = {"clock"}
    before = digest_of(live_rows(content).values())
    base = entity_snapshot(content, index_entities(content), event, lambda kind, key: str(key))
    content.clock_readings[(event, clock)] = {
        "data": {"lo": "1", "hi": "1", "lo_inclusive": True, "hi_inclusive": True},
        "is_shared": False,
    }
    assert before != digest_of(live_rows(content).values())
    upstream = entity_snapshot(content, index_entities(content), event, lambda kind, key: str(key))
    changes = diff(base, upstream, base, {})
    assert [c.field for c in changes] == ["clock_readings"]
    local = deepcopy(upstream)
    local["clock_readings"][0]["data"]["lo"] = "2"
    local["clock_readings"][0]["data"]["hi"] = "2"
    assert diff(base, upstream, local, {})[0].state == "conflict"


async def test_event_deletion_and_reading_creation_have_clean_race_outcomes(client, test_user_id):
    import asyncio

    t = await make_tenant(test_user_id)
    try:
        clock = await make_clock(client, t)
        cid = clock.json()["entity_id"]
        event = await client.post(
            f"/tenants/{t}/entities", json={"name": "Departure", "kinds": ["event"]}
        )
        eid = event.json()["id"]
        route = f"/tenants/{t}/events/{eid}/clock-readings"
        version = (await client.get(route)).headers["etag"]
        written, removed = await asyncio.gather(
            client.put(
                route + f"/{cid}",
                json={"reading": {"lo": "1", "hi": "1"}},
                headers={"If-Match": version},
            ),
            client.delete(f"/tenants/{t}/entities/{eid}"),
        )
        assert (written.status_code, removed.status_code) in [(200, 409), (404, 204)], (
            written.text,
            removed.text,
        )
    finally:
        await delete_tenant(t)
