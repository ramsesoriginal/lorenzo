"""Explicit lived evidence, independent support, privacy and mixed graph integrity."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from test_session_play import event
from test_story_sessions import world

from lorenzo_api.models import EventLearning


async def being(w, name="Mara"):
    result = await w.owner.post(
        f"/tenants/{w.tenant_id}/entities", json={"name": name, "kinds": ["being"]}
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


async def participate(w, b, events):
    for e in events:
        base = f"/tenants/{w.tenant_id}/events/{e}/participants"
        version = (await w.author.get(base)).headers["etag"]
        response = await w.author.client.put(
            base + f"/{b}", headers={**w.author.headers, "If-Match": version}
        )
        assert response.status_code == 200, response.text


async def lived(w, b, a, z, shared=False, version=None):
    url = f"/tenants/{w.tenant_id}/beings/{b}/lived-order"
    version = version or (await w.author.get(url)).headers["etag"]
    return await w.author.client.put(
        url,
        headers={**w.author.headers, "If-Match": version},
        json={"assertions": [{"from_event_id": a, "to_event_id": z, "is_shared": shared}]},
    )


async def compare(w, a, b, reader=False):
    actor = w.outsider if reader else w.author
    result = await actor.post(
        f"/tenants/{w.tenant_id}/events/compare", json={"pairs": [{"left": a, "right": b}]}
    )
    assert result.status_code == 200, result.text
    return result.json()[0]


async def remove(w, b, a, z):
    url = f"/tenants/{w.tenant_id}/beings/{b}/lived-order"
    version = (await w.author.get(url)).headers["etag"]
    return await w.author.client.delete(
        url + f"/{a}/{z}", headers={**w.author.headers, "If-Match": version}
    )


async def test_lived_support_is_explicit_private_and_independently_removable(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        a, z = await event(w, "Arrival"), await event(w, "Departure")
        mara, ivo = await being(w), await being(w, "Ivo")
        for b in [mara, ivo]:
            await participate(w, b, [a, z])
        url = f"/tenants/{w.tenant_id}/beings/{mara}/lived-order"
        assert (await w.author.get(url)).json()["assertions"] == []
        result = await lived(w, mara, a, z)
        assert result.status_code == 200, result.text
        proof = await compare(w, a, z)
        assert proof["basis"] == "ruled" and proof["path"][0]["evidence"] == "lived"
        assert proof["path"][0]["being_entity_id"] == mara
        assert (await compare(w, a, z, True))["basis"] == "linearized"
        assert (await w.outsider.get(url)).json()["assertions"] == []
        assert (await lived(w, mara, a, z, True)).status_code == 200
        assert (await compare(w, a, z, True))["path"][0]["being_name"] == "Mara"
        assert (await lived(w, ivo, a, z, True)).status_code == 200
        assert (await remove(w, mara, a, z)).status_code == 200
        proof = await compare(w, a, z, True)
        assert proof["path"][0]["being_entity_id"] == ivo
        # Ordinary support remains a separate row and survives both lived sources.
        base = f"/tenants/{w.tenant_id}/events/{a}/relationships"
        version = (await w.author.get(base)).headers["etag"]
        ordinary = await w.author.client.put(
            base + f"/{z}",
            headers={**w.author.headers, "If-Match": version},
            json={"kind": "order"},
        )
        assert ordinary.status_code == 200
        assert (await remove(w, ivo, a, z)).status_code == 200
        assert (await compare(w, a, z))["path"][0]["evidence"] == "assertion"
        async with admin_session_factory() as db:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(EventLearning)
                    .where(EventLearning.tenant_id == w.tenant_id)
                )
                == 0
            )
    finally:
        await w.clean_up()


async def test_lived_cycles_missing_participation_stale_writes_and_participation_deletion(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        a, z, third = (
            await event(w, "First"),
            await event(w, "Second"),
            await event(w, "Unexperienced"),
        )
        b = await being(w)
        await participate(w, b, [a, z])
        assert (await lived(w, b, a, third)).status_code == 404
        url = f"/tenants/{w.tenant_id}/beings/{b}/lived-order"
        old = (await w.author.get(url)).headers["etag"]
        results = await asyncio.gather(
            lived(w, b, a, z, version=old), lived(w, b, a, z, version=old)
        )
        assert sorted(r.status_code for r in results) == [200, 412]
        assert (await lived(w, b, z, a)).status_code == 409
        assert (await lived(w, b, a, a)).status_code == 409
        endpoint = f"/tenants/{w.tenant_id}/events/{a}/participants"
        version = (await w.author.get(endpoint)).headers["etag"]
        refused = await w.author.client.delete(
            endpoint + f"/{b}", headers={**w.author.headers, "If-Match": version}
        )
        assert refused.status_code == 409
        assert "lived" not in refused.text.lower()
        assert (await remove(w, b, a, z)).status_code == 200
        version = (await w.author.get(endpoint)).headers["etag"]
        assert (
            await w.author.client.delete(
                endpoint + f"/{b}", headers={**w.author.headers, "If-Match": version}
            )
        ).status_code == 200
        # Players remain readers, even when they can author their own Events.
        denied = await w.outsider.client.put(
            url,
            headers={**w.outsider.headers, "If-Match": old},
            json={"assertions": [{"from_event_id": a, "to_event_id": z}]},
        )
        assert denied.status_code == 403
    finally:
        await w.clean_up()


async def test_database_serializes_mixed_raw_lived_and_causal_cycles(raw_client, fake_jwks_server):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        a, z = await event(w, "A"), await event(w, "Z")
        b = await being(w)
        await participate(w, b, [a, z])
        insert = text(
            "INSERT INTO lived_before(tenant_id,being_entity_id,from_event_id,to_event_id) "
            "VALUES(:t,:b,:a,:z)"
        )
        reverse = text(
            "INSERT INTO event_relationship(tenant_id,from_event_id,to_event_id,kind) "
            "VALUES(:t,:z,:a,'causes')"
        )
        values = {"t": w.tenant_id, "b": uuid.UUID(b), "a": uuid.UUID(a), "z": uuid.UUID(z)}
        async with admin_session_factory() as first, admin_session_factory() as second:
            await first.execute(insert, values)
            task = asyncio.create_task(second.execute(reverse, values))
            await asyncio.sleep(0.1)
            assert not task.done()
            await first.commit()
            with pytest.raises(IntegrityError, match="acyclic"):
                await task
            await second.rollback()
        async with admin_session_factory() as db:
            with pytest.raises(IntegrityError):
                await db.execute(
                    text("UPDATE lived_before SET from_event_id=to_event_id WHERE tenant_id=:t"),
                    values,
                )
            await db.rollback()
            with pytest.raises(IntegrityError):
                await db.execute(insert, {**values, "b": uuid.uuid4()})
                await db.commit()
            await db.rollback()
        async with admin_session_factory() as db:
            await db.execute(text("DELETE FROM lived_before WHERE tenant_id=:t"), values)
            await db.commit()
        swapped = {**values, "a": values["z"], "z": values["a"]}
        async with admin_session_factory() as first, admin_session_factory() as second:
            await first.execute(reverse, swapped)
            task = asyncio.create_task(second.execute(insert, swapped))
            await asyncio.sleep(0.1)
            assert not task.done()
            await first.commit()
            with pytest.raises(IntegrityError, match="acyclic"):
                await task
            await second.rollback()
    finally:
        await w.clean_up()


async def test_hidden_being_support_is_removed_before_derivation(raw_client, fake_jwks_server):
    from lorenzo_api.models import EntityAudience

    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        a, z = await event(w, "A"), await event(w, "Z")
        b = await being(w)
        await participate(w, b, [a, z])
        assert (await lived(w, b, a, z, True)).status_code == 200
        # Exercise an existing stored outer gate without introducing a Being-gate UI.
        async with admin_session_factory() as db:
            db.add(EntityAudience(tenant_id=w.tenant_id, entity_id=uuid.UUID(b), is_public=False))
            await db.commit()
        result = await compare(w, a, z, True)
        assert result["basis"] == "linearized" and result["path"] == []
        assert (
            await w.outsider.get(f"/tenants/{w.tenant_id}/beings/{b}/lived-order")
        ).status_code == 404
    finally:
        await w.clean_up()


async def test_lived_copy_release_and_purge_remap_existing_participations(
    raw_client, fake_jwks_server
):
    from _repository_actors import cleanup
    from _repository_fixtures import seed_every_content_table

    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content

    w, c, p = await world(raw_client, fake_jwks_server)
    repository = await w.owner.create_tenant("Lived repository", kind="repository")
    try:
        async with admin_session_factory() as db:
            await seed_every_content_table(db, repository)
            await db.commit()
            original = await load_content(db, repository)
            document, files = encode(original)
            assert decode(document, files).lived_before == original.lived_before
        assert (
            await w.owner.put(f"/tenants/{repository}/subscribers/{w.tenant_id}")
        ).status_code in (200, 201)
        assert (await w.owner.put(f"/tenants/{repository}/published")).status_code == 200
        url = f"/tenants/{w.tenant_id}/repositories/{repository}/copy"
        copied = await w.owner.post(url, json={})
        assert copied.status_code == 201, copied.text
        async with admin_session_factory() as db:
            content = await load_content(db, w.tenant_id)
            assert len(content.lived_before) == 1
            b, a, z, shared = content.lived_before[0]
            assert (
                shared
                and (a, b) in content.event_participants
                and (z, b) in content.event_participants
            )
            assert {b, a, z}.isdisjoint(set(original.entities))
            old = b
        purged = await w.owner.post(url, json={"again": "purge"})
        assert purged.status_code == 201, purged.text
        async with admin_session_factory() as db:
            content = await load_content(db, w.tenant_id)
            assert old not in content.entities and len(content.lived_before) == 1
    finally:
        await cleanup([repository], [])
        await w.clean_up()


async def test_reviewed_lived_proposal_is_atomic_when_its_pairs_conflict(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        a, z = await event(w, "A"), await event(w, "Z")
        b = await being(w)
        await participate(w, b, [a, z])
        url = f"/tenants/{w.tenant_id}/beings/{b}/lived-order"
        version = (await w.author.get(url)).headers["etag"]
        response = await w.author.client.put(
            url,
            headers={**w.author.headers, "If-Match": version},
            json={
                "assertions": [
                    {"from_event_id": a, "to_event_id": z},
                    {"from_event_id": z, "to_event_id": a},
                ]
            },
        )
        assert response.status_code == 409
        assert (await w.author.get(url)).json()["assertions"] == []
        assert (await compare(w, a, z))["basis"] == "linearized"
    finally:
        await w.clean_up()
