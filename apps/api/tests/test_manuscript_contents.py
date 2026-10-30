"""Contents remain reader-scoped navigation, never generated prose (ADR 0381)."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import text

from lorenzo_api.manuscript_contents import ContentsSettings
from lorenzo_api.models import EntityAudience, Player


@pytest.mark.parametrize(
    "template", ["{title} {title}", "{unknown}", "{title} {number} {number}", "{title} {", "plain"]
)
def test_invalid_templates(template: str) -> None:
    with pytest.raises(ValidationError):
        ContentsSettings(template=template)


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_contents_roles_depth_copy_and_review(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    from conftest import delete_tenant, make_campaign

    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    writing = base + "/writing"
    target = None
    try:
        book = (await actor.post(writing + "/books", json={"name": "River book"})).json()
        edition = book["editions"][0]["id"]
        contents, first, nested, glossary = [
            (await actor.post(writing + "/chapters", json={"name": name})).json()["id"]
            for name in ("Contents", "Crossing", "Ferry", "Glossary")
        ]

        async def arrange(id: str, children: list[str]):
            view = (await actor.get(writing + f"/entries/{id}")).json()
            response = await raw_client.put(
                writing + f"/entries/{id}/composition",
                headers={**actor.headers, "If-Match": view["version"]},
                json={"elements": children},
            )
            assert response.status_code == 200, response.text

        async def read(id: str):
            response = await actor.get(writing + f"/entries/{id}/contents")
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "private, no-store"
            return response.json()

        async def save(id: str, **changes):
            view = await read(id)
            response = await raw_client.put(
                writing + f"/entries/{id}/contents",
                headers={**actor.headers, "If-Match": view["version"]},
                json={**view["settings"], **changes},
            )
            assert response.status_code == 200, response.text
            return response.json()

        await arrange(edition, [contents, first, glossary])
        await arrange(first, [nested])
        prose = await actor.post(
            base + f"/entities/{glossary}/information",
            json={
                "title": "Manuscript",
                "type": "manuscript",
                "content": "**Ferry**: a boat crossing the river.",
            },
        )
        assert prose.status_code == 201
        number_url = writing + f"/entries/{edition}/numbering"
        number_view = (await actor.get(number_url)).json()
        numbered = await raw_client.put(
            number_url,
            headers={**actor.headers, "If-Match": number_view["version"]},
            json={"enabled": True},
        )
        assert numbered.status_code == 200, numbered.text
        default = await read(edition)
        assert [row["label"] for row in default["rows"]] == [
            "1 Contents",
            "2 Crossing",
            "2.1 Ferry",
            "3 Glossary",
        ]
        assert default["displayed"] is False
        url = writing + f"/entries/{edition}/contents"
        body = {**default["settings"], "enabled": True}
        assert (await actor.put(url, json=body)).status_code == 428
        made = await raw_client.put(
            url, headers={**actor.headers, "If-Match": default["version"]}, json=body
        )
        assert made.status_code == 200, made.text
        assert [(r["id"], r["depth"]) for r in made.json()["rows"]] == [
            (contents, 1),
            (first, 1),
            (nested, 2),
            (glossary, 1),
        ]
        assert (
            await raw_client.put(
                url, headers={**actor.headers, "If-Match": default["version"]}, json=body
            )
        ).status_code == 200
        assert (
            await raw_client.put(
                url,
                headers={**actor.headers, "If-Match": default["version"]},
                json={**body, "depth": 1},
            )
        ).status_code == 412
        assert (
            await raw_client.put(
                url,
                headers={**actor.headers, "If-Match": made.json()["version"]},
                json={**body, "role": "glossary"},
            )
        ).status_code == 422
        await save(contents, role="contents", included=False)
        await save(first, included=False)
        view = await save(glossary, role="glossary")
        assert [r["id"] for r in view["rows"]] == [nested, glossary]
        assert view["settings"]["role"] == "glossary"
        assert (await actor.get(base + f"/entities/{glossary}")).json()["information"][0][
            "payloads"
        ][0]["content"] == "**Ferry**: a boat crossing the river."
        await save(edition, depth=1)
        assert [r["id"] for r in (await read(edition))["rows"]] == [glossary]
        await save(edition, depth=3, enabled=False, template="<b>{title}</b>")
        special = await read(contents)
        assert special["displayed"] is True and contents in special["contents_chapters"]
        assert [r["label"] for r in special["rows"]] == ["<b>Ferry</b>", "<b>Glossary</b>"]
        review = writing + f"/reviews/{edition}"
        assert (await actor.put(review + f"/reviewers/{world.outsider.user_id}")).status_code == 204
        reviewed = await world.outsider.get(review)
        assert reviewed.status_code == 200, reviewed.text
        by_id = {e["id"]: e for e in reviewed.json()["entries"]}
        assert by_id[edition]["contents"] is None
        assert [r["id"] for r in by_id[contents]["contents"]] == [nested, glossary]
        assert (await world.outsider.get(url)).status_code == 404
        assert (
            await actor.delete(review + f"/reviewers/{world.outsider.user_id}")
        ).status_code == 204
        assert (await world.outsider.get(review)).status_code == 404
        if kind == "play":
            # Regular readers must not learn about an invisible branch or its settings.
            async with admin_session_factory() as session:
                campaign = await make_campaign(session, tenant_id=world.tenant_id)
                session.add(
                    Player(
                        tenant_id=world.tenant_id,
                        campaign_id=campaign.id,
                        user_id=world.outsider.user_id,
                    )
                )
                for id in (edition, glossary, nested):
                    (await session.get(EntityAudience, uuid.UUID(id))).is_public = True
                await session.commit()
                assert (
                    await session.scalar(
                        text(
                            "SELECT relforcerowsecurity FROM pg_class "
                            "WHERE relname='manuscript_contents'"
                        )
                    )
                    is True
                )
            visible = await world.outsider.get(url)
            assert visible.status_code == 200, visible.text
            assert [r["id"] for r in visible.json()["rows"]] == [glossary]
            assert (
                first not in visible.text
                and nested not in visible.text
                and contents not in visible.text
            )
            orphan = await world.outsider.get(writing + f"/entries/{nested}/contents")
            assert orphan.json()["root_id"] == nested and first not in orphan.text
            assert (await world.outsider.put(url, json=body)).status_code == 403
        # Independent Edition copy retains role and navigation settings.
        cloned = await actor.post(
            writing + "/editions", json={"name": "Second edition", "source_edition_id": edition}
        )
        assert cloned.status_code == 201, cloned.text
        clone = await read(cloned.json()["id"])
        assert [r["label"] for r in clone["rows"]] == ["<b>Ferry</b>", "<b>Glossary</b>"]
        assert len(clone["contents_chapters"]) == 1
        await save(edition, template="{title}")
        assert (await read(cloned.json()["id"]))["settings"]["template"] == "<b>{title}</b>"
        if kind == "repository":
            target = await world.owner.create_tenant("Contents copy")
            assert (await world.owner.put(base + f"/subscribers/{target}")).status_code in (
                200,
                201,
            )
            assert (await world.owner.put(base + "/published")).status_code == 200
            copied = await world.owner.post(
                f"/tenants/{target}/repositories/{world.tenant_id}/copy"
            )
            assert copied.status_code == 201, copied.text
            entries = (
                await world.owner.get(f"/tenants/{target}/entities", params={"size": 100})
            ).json()["items"]
            local = next(
                e for e in entries if e["name"] == "Second edition" and "edition" in e["kinds"]
            )
            local_view = await world.owner.get(
                f"/tenants/{target}/writing/entries/{local['id']}/contents"
            )
            assert local_view.status_code == 200, local_view.text
            assert [r["label"] for r in local_view.json()["rows"]] == [
                "<b>Ferry</b>",
                "<b>Glossary</b>",
            ]
            assert all(r["id"] not in (nested, glossary) for r in local_view.json()["rows"])
            assert (
                await world.owner.get(f"/tenants/{target}/writing/entries/{edition}/contents")
            ).status_code == 404
        current = await read(edition)
        results = await asyncio.gather(
            *[
                raw_client.put(
                    url,
                    headers={**actor.headers, "If-Match": current["version"]},
                    json={**current["settings"], "depth": depth},
                )
                for depth in (1, 2)
            ]
        )
        assert sorted(r.status_code for r in results) == [200, 412]
        # An unassigned Chapter supplies its own root policy for its retained subtree.
        await arrange(edition, [contents, glossary])
        standalone = await save(first, enabled=True, depth=1, template="{title}", role="index")
        assert standalone["root_id"] == first and standalone["displayed"] is True
        assert [(row["label"], row["depth"]) for row in standalone["rows"]] == [("Ferry", 1)]
    finally:
        if target:
            await delete_tenant(target)
        await world.clean_up()
