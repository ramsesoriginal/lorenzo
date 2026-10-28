"""Review grants disclose only selected manuscripts and fixed-audience notes."""

import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import text

from lorenzo_api.models import Payload, PayloadPicture


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_review_scope_notes_pictures_and_revocation(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    reviewer = world.outsider
    other = await make_actor(raw_client, fake_jwks_server, "other-reviewer", roles=())
    base = f"/tenants/{world.tenant_id}"
    copied_tenant = None
    try:
        book = (
            await world.author.post(base + "/writing/books", json={"name": "The crossing"})
        ).json()
        edition = book["editions"][0]["id"]
        scene = (
            await world.author.post(base + "/scenes", json={"name": "Private Scene identity"})
        ).json()["id"]
        manuscript = await world.author.post(
            base + f"/entities/{scene}/information",
            json={"type": "manuscript", "title": "Manuscript", "content": "The river remembers."},
        )
        assert manuscript.status_code == 201, manuscript.text
        secret = await world.author.post(
            base + f"/entities/{scene}/information",
            json={"type": "note", "title": "Research", "content": "Unrelated secret"},
        )
        assert secret.status_code == 201, secret.text
        picture_id = uuid.uuid4()
        async with admin_session_factory() as session:
            session.add(
                Payload(
                    id=picture_id,
                    tenant_id=world.tenant_id,
                    information_id=uuid.UUID(manuscript.json()["id"]),
                    order=1,
                )
            )
            await session.flush()
            session.add(
                PayloadPicture(
                    payload_id=picture_id,
                    tenant_id=world.tenant_id,
                    data=b"protected picture",
                    file_type="image/png",
                )
            )
            await session.commit()
        telling = (
            await world.author.post(
                base + "/writing/tellings", json={"name": "Across the water", "scene_id": scene}
            )
        ).json()["id"]
        chapter = (
            await world.author.post(base + "/writing/chapters", json={"name": "Chapter one"})
        ).json()["id"]
        for parent, child in [(chapter, telling), (edition, chapter)]:
            current = (await world.author.get(base + f"/writing/entries/{parent}")).json()
            placed = await raw_client.put(
                base + f"/writing/entries/{parent}/composition",
                headers={**world.author.headers, "If-Match": current["version"]},
                json={"elements": [child]},
            )
            assert placed.status_code == 200, placed.text
        url = base + f"/writing/reviews/{edition}"
        assert (await reviewer.get(url)).status_code == 404
        for actor in [reviewer, other]:
            granted = await world.author.put(url + f"/reviewers/{actor.user_id}")
            assert granted.status_code == 204, granted.text
            assert (await world.author.put(url + f"/reviewers/{actor.user_id}")).status_code == 204
        review = await reviewer.get(url)
        assert review.status_code == 200, review.text
        assert review.headers["cache-control"] == "private, no-store"
        assert {entry["id"] for entry in review.json()["entries"]} == {edition, chapter, telling}
        assert "The river remembers." in review.text
        assert (
            "Unrelated secret" not in review.text
            and "Private Scene identity" not in review.text
            and scene not in review.text
        )
        picture_url = url + f"/pictures/{picture_id}"
        image = await reviewer.get(picture_url)
        assert image.status_code == 200 and image.content == b"protected picture"
        assert image.headers["cache-control"] == "private, no-store"
        # The grant is not membership, manuscript editing, resolution or access to source notes.
        for path in [
            f"/entities/{scene}",
            f"/entities/{telling}",
            f"/information/{manuscript.json()['id']}",
            f"/information/{manuscript.json()['id']}/editor",
            f"/payloads/{picture_id}/content",
            "/entities",
            f"/writing/entries/{edition}",
        ]:
            denied = await reviewer.get(base + path)
            assert denied.status_code in {403, 404}, (path, denied.text)
        assert (await reviewer.put(url + f"/reviewers/{world.owner.user_id}")).status_code in {
            403,
            404,
        }
        note_id = uuid.uuid4()
        note_url = url + f"/notes/{note_id}"
        note_body = {"entry_id": telling, "content": "**Does the ferryman know?**"}
        made = await reviewer.put(note_url, json=note_body)
        assert made.status_code == 201, made.text
        assert (await reviewer.put(note_url, json=note_body)).status_code == 200
        assert (await other.get(url)).json()["notes"] == []
        assert (await world.author.get(url)).json()["notes"][0]["id"] == str(note_id)
        assert (await other.put(note_url, json=note_body)).status_code == 404
        changed = {**note_body, "content": "A revised question"}
        assert (await reviewer.put(note_url, json=changed)).status_code == 428
        updated = await raw_client.put(
            note_url, headers={**reviewer.headers, "If-Match": "1"}, json=changed
        )
        assert updated.status_code == 200, updated.text
        stale = await raw_client.put(
            note_url, headers={**reviewer.headers, "If-Match": "1"}, json=note_body
        )
        assert stale.status_code == 412
        clone = (
            await world.author.post(
                base + "/writing/editions",
                json={"name": "Other edition", "source_edition_id": edition},
            )
        ).json()["id"]
        assert (await reviewer.get(base + f"/writing/reviews/{clone}")).status_code == 404
        assert (await world.author.get(base + f"/writing/reviews/{clone}/reviewers")).json() == []
        if kind == "repository":
            from sqlalchemy import select

            from lorenzo_api.models import Edition, WritingReviewGrant, WritingReviewNote

            copied_tenant = await world.owner.create_tenant("Copy without review access")
            assert (await world.owner.put(base + f"/subscribers/{copied_tenant}")).status_code in {
                200,
                201,
            }
            assert (await world.owner.put(base + "/published")).status_code == 200
            copied = await world.owner.post(
                f"/tenants/{copied_tenant}/repositories/{world.tenant_id}/copy"
            )
            assert copied.status_code == 201, copied.text
            async with admin_session_factory() as session:
                for model in (WritingReviewGrant, WritingReviewNote):
                    assert not list(
                        await session.scalars(select(model).where(model.tenant_id == copied_tenant))
                    )
                target = await session.scalar(
                    select(Edition.entity_id).where(Edition.tenant_id == copied_tenant)
                )
            assert target is not None
            collision = await world.owner.put(
                f"/tenants/{copied_tenant}/writing/reviews/{target}/notes/{note_id}",
                json={"entry_id": str(target), "content": "Other library"},
            )
            assert collision.status_code == 409, collision.text
        # Removing a subtree removes its text, pictures and notes from reviewer scope.
        current = (await world.author.get(base + f"/writing/entries/{edition}")).json()
        detached = await raw_client.put(
            base + f"/writing/entries/{edition}/composition",
            headers={**world.author.headers, "If-Match": current["version"]},
            json={"elements": []},
        )
        assert detached.status_code == 200
        assert (await reviewer.get(picture_url)).status_code == 404
        assert (await reviewer.get(url)).json()["notes"] == []
        assert len((await world.author.get(url)).json()["notes"]) == 1
        assert (await reviewer.put(note_url, json=changed)).status_code == 404
        assert (
            await world.author.delete(url + f"/reviewers/{reviewer.user_id}")
        ).status_code == 204
        assert (await reviewer.get(url)).status_code == 404
        assert (
            await raw_client.get(picture_url, headers={**reviewer.headers, "If-None-Match": "*"})
        ).status_code == 404
        assert (
            await reviewer.put(
                url + f"/notes/{uuid.uuid4()}", json={"entry_id": edition, "content": "Late note"}
            )
        ).status_code == 404
        assert (await other.get(url)).status_code == 200
        farewell = await other.put(
            url + f"/notes/{uuid.uuid4()}",
            json={"entry_id": edition, "content": "Keep this feedback after my account is gone"},
        )
        assert farewell.status_code == 201, farewell.text
        await cleanup([], [other])
        retained = (await world.author.get(url)).json()["notes"]
        assert any(
            n["author_id"] is None and n["content"] == "Keep this feedback after my account is gone"
            for n in retained
        )
    finally:
        if copied_tenant is not None:
            await cleanup([copied_tenant], [])
        await world.clean_up()
        await cleanup([], [other])


async def test_review_tables_force_rls_and_are_not_repository_content() -> None:
    from lorenzo_api.copyable_tables import EXCLUDED_TABLES

    assert {"writing_review_grant", "writing_review_note"} <= EXCLUDED_TABLES
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname IN ('writing_review_grant', 'writing_review_note')"
                )
            )
        ).all()
    assert len(rows) == 2
    assert all(enabled and forced for _, enabled, forced in rows)
