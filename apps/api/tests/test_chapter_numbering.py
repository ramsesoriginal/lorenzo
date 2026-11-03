"""Numbering is presentation over authorized composition (ADR 0380)."""

import uuid

import pytest
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient

from lorenzo_api.chapter_numbering import NumberingLevel, NumberingSettings, calculate, numeral


@pytest.mark.parametrize(
    ("value", "style", "expected"),
    [
        (4, "roman", "IV"),
        (49, "roman_lower", "xlix"),
        (4000, "roman", "4000"),
        (27, "alphabetic", "AA"),
        (703, "alphabetic_lower", "aaa"),
        (12, "decimal", "12"),
    ],
)
def test_number_formats(value: int, style: str, expected: str) -> None:
    assert numeral(value, style) == expected


def test_levels_boundaries_and_unnumbered_parents() -> None:
    root, a, b, c, d, aa, ba = [uuid.uuid4() for _ in range(7)]
    ordered = {root: [a, b, c, d], a: [aa], b: [ba]}
    chapters = {a, b, c, d, aa, ba}
    settings = {
        root: NumberingSettings(
            enabled=True,
            levels=[
                NumberingLevel(style="roman", start=3),
                NumberingLevel(style="alphabetic_lower", restart_per_parent=False),
            ],
        )
    }
    assert calculate(root, chapters, ordered, settings) == {
        a: "III",
        aa: "III.a",
        b: "IV",
        ba: "IV.b",
        c: "V",
        d: "VI",
    }
    settings[a] = NumberingSettings(unnumbered=True)
    settings[b] = NumberingSettings(override=9, end=True)
    settings[d] = NumberingSettings(restart=True)
    assert calculate(root, chapters, ordered, settings) == {aa: "a", b: "IX", ba: "IX.b", d: "III"}
    settings[root].levels[1].restart_per_parent = True
    assert calculate(root, chapters, ordered, settings)[ba] == "IX.a"
    settings[root].levels[1].include_parents = False
    assert calculate(root, chapters, ordered, settings)[ba] == "a"
    # Prune an inaccessible parent and its descendants, without a numbering gap.
    assert calculate(root, chapters - {b}, ordered, settings) == {aa: "a", c: "III", d: "III"}


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_numbering_order_conditions_copy_and_review(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    writing = base + "/writing"
    target = None
    try:
        book = (await actor.post(writing + "/books", json={"name": "Numbered book"})).json()
        edition = book["editions"][0]["id"]
        a, b, aa = [
            (await actor.post(writing + "/chapters", json={"name": name})).json()["id"]
            for name in ("First", "Second", "Nested")
        ]

        async def arrange(parent: str, ids: list[str]) -> None:
            view = (await actor.get(writing + f"/entries/{parent}")).json()
            response = await raw_client.put(
                writing + f"/entries/{parent}/composition",
                headers={**actor.headers, "If-Match": view["version"]},
                json={"elements": ids},
            )
            assert response.status_code == 200, response.text

        async def read(id: str):
            response = await actor.get(writing + f"/entries/{id}/numbering")
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "private, no-store"
            return response.json()

        async def save(id: str, **changes):
            view = await read(id)
            response = await raw_client.put(
                writing + f"/entries/{id}/numbering",
                headers={**actor.headers, "If-Match": view["version"]},
                json={**view["settings"], **changes},
            )
            assert response.status_code == 200, response.text
            return response.json()

        await arrange(edition, [a, b])
        await arrange(a, [aa])
        assert (await read(edition))["labels"] == {}
        url = writing + f"/entries/{edition}/numbering"
        old = await read(edition)
        body = {
            **old["settings"],
            "enabled": True,
            "levels": [{"style": "roman"}, {"style": "alphabetic_lower"}],
        }
        assert (await actor.put(url, json=body)).status_code == 428
        made = await raw_client.put(
            url, headers={**actor.headers, "If-Match": old["version"]}, json=body
        )
        assert made.status_code == 200, made.text
        assert made.json()["labels"] == {a: "I", aa: "I.a", b: "II"}
        retry = await raw_client.put(
            url, headers={**actor.headers, "If-Match": old["version"]}, json=body
        )
        assert retry.status_code == 200
        stale = await raw_client.put(
            url,
            headers={**actor.headers, "If-Match": old["version"]},
            json={**body, "enabled": False},
        )
        assert stale.status_code == 412
        invalid = await raw_client.put(
            url,
            headers={**actor.headers, "If-Match": made.json()["version"]},
            json={**body, "levels": [{"start": 0}]},
        )
        assert invalid.status_code == 422
        await save(a, override=5)
        assert (await read(aa))["root_id"] == edition
        assert (await read(aa))["labels"] == {a: "V", aa: "V.a", b: "VI"}
        await arrange(edition, [b, a])
        assert (await read(edition))["labels"] == {b: "I", a: "V", aa: "V.a"}
        await save(a, unnumbered=True)
        assert (await read(edition))["labels"] == {b: "I", aa: "a"}
        assert (await world.outsider.get(url)).status_code == 404
        review = writing + f"/reviews/{edition}"
        assert (await actor.put(review + f"/reviewers/{world.outsider.user_id}")).status_code == 204
        reviewed = await world.outsider.get(review)
        assert reviewed.status_code == 200, reviewed.text
        assert {e["id"]: e["number"] for e in reviewed.json()["entries"] if e["number"]} == {
            b: "I",
            aa: "a",
        }
        assert (await world.outsider.put(url, json=body)).status_code in (403, 404)
        assert (
            await actor.delete(review + f"/reviewers/{world.outsider.user_id}")
        ).status_code == 204
        assert (await world.outsider.get(review)).status_code == 404
        duplicate = await actor.post(
            writing + "/editions", json={"name": "Independent", "source_edition_id": edition}
        )
        assert duplicate.status_code == 201, duplicate.text
        clone = duplicate.json()
        assert set((await read(clone["id"]))["labels"].values()) == {"I", "a"}
        await save(edition, enabled=False)
        assert (await read(clone["id"]))["labels"]
        if kind == "repository":
            target = await world.owner.create_tenant("Numbering copy")
            assert (await world.owner.put(base + f"/subscribers/{target}")).status_code in (
                200,
                201,
            )
            published = await world.owner.put(base + "/published")
            assert published.status_code == 200, published.text
            copied = await world.owner.post(
                f"/tenants/{target}/repositories/{world.tenant_id}/copy"
            )
            assert copied.status_code == 201, copied.text
            entries = (
                await world.owner.get(f"/tenants/{target}/entities", params={"size": 100})
            ).json()["items"]
            local = next(
                e for e in entries if e["name"] == "Independent" and "edition" in e["kinds"]
            )
            response = await world.owner.get(
                f"/tenants/{target}/writing/entries/{local['id']}/numbering"
            )
            assert response.status_code == 200, response.text
            assert set(response.json()["labels"].values()) == {"I", "a"}
            assert set(response.json()["labels"]).isdisjoint({a, b, aa})
            assert (
                await world.owner.get(f"/tenants/{target}/writing/entries/{edition}/numbering")
            ).status_code == 404
    finally:
        if target:
            from conftest import delete_tenant

            await delete_tenant(target)
        await world.clean_up()


async def test_hidden_branches_anchor_order_and_rls(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    from _admin_db import admin_session_factory
    from conftest import make_campaign
    from sqlalchemy import text

    from lorenzo_api.models import EntityAudience, ManuscriptNumbering, ManuscriptPlacement, Player

    world = await make_world(raw_client, fake_jwks_server)
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    try:
        book = (await actor.post(base + "/writing/books", json={"name": "Visible book"})).json()
        edition = book["editions"][0]["id"]
        hidden, visible, nested = [
            (await actor.post(base + "/writing/chapters", json={"name": name})).json()["id"]
            for name in ("Hidden", "Visible", "Visible below hidden")
        ]
        prose = (
            await actor.post(
                base + f"/entities/{edition}/information",
                json={"type": "manuscript", "title": "Text", "content": "Between chapters"},
            )
        ).json()
        anchor = prose["payloads"][0]["id"]
        # After a payload reorder, following anchors take precedence over stored positions.
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=world.tenant_id)
            session.add(
                Player(
                    tenant_id=world.tenant_id,
                    campaign_id=campaign.id,
                    user_id=world.outsider.user_id,
                )
            )
            for id in (edition, visible, nested):
                (await session.get(EntityAudience, uuid.UUID(id))).is_public = True
            session.add(
                ManuscriptNumbering(
                    entity_id=uuid.UUID(edition),
                    tenant_id=world.tenant_id,
                    settings={"enabled": True},
                )
            )
            session.add_all(
                [
                    ManuscriptPlacement(
                        tenant_id=world.tenant_id,
                        child_entity_id=uuid.UUID(hidden),
                        parent_entity_id=uuid.UUID(edition),
                        before_payload_id=uuid.UUID(anchor),
                        position=9,
                    ),
                    ManuscriptPlacement(
                        tenant_id=world.tenant_id,
                        child_entity_id=uuid.UUID(visible),
                        parent_entity_id=uuid.UUID(edition),
                        before_payload_id=None,
                        position=0,
                    ),
                    ManuscriptPlacement(
                        tenant_id=world.tenant_id,
                        child_entity_id=uuid.UUID(nested),
                        parent_entity_id=uuid.UUID(hidden),
                        before_payload_id=None,
                        position=0,
                    ),
                ]
            )
            await session.commit()
            forced = await session.scalar(
                text(
                    "SELECT relforcerowsecurity FROM pg_class WHERE relname='manuscript_numbering'"
                )
            )
            assert forced is True
        url = base + f"/writing/entries/{edition}/numbering"
        assert (await actor.get(url)).json()["labels"] == {hidden: "1", nested: "1.1", visible: "2"}
        reader = await world.outsider.get(url)
        assert reader.status_code == 200, reader.text
        assert reader.json()["labels"] == {visible: "1"}
        assert hidden not in reader.text and nested not in reader.text
        orphan = await world.outsider.get(base + f"/writing/entries/{nested}/numbering")
        assert orphan.status_code == 200, orphan.text
        assert orphan.json()["root_id"] == nested and hidden not in orphan.text
        assert (await world.outsider.put(url, json={"enabled": False})).status_code == 403
        # Competing different writes cannot both replace the same settings version.
        import asyncio

        original = (await actor.get(url)).json()
        writes = await asyncio.gather(
            *[
                raw_client.put(
                    url,
                    headers={**actor.headers, "If-Match": original["version"]},
                    json={"enabled": True, "levels": [{"start": start}]},
                )
                for start in (3, 7)
            ]
        )
        assert sorted(r.status_code for r in writes) == [200, 412]
    finally:
        await world.clean_up()
