"""A repository's life through the real HTTP API, authoring included:
its content is written through the ordinary routes, as its members would
(ADR 0118). Then ADR 0119's dry runs, contributions, and copying again,
and ADR 0121's dry run.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from lorenzo_api.models import AuditLog, Entity, EntityStat, StatDefinition


def _id(response: Response) -> str:
    assert response.status_code in (200, 201), response.text
    body: dict[str, Any] = response.json()
    return str(body.get("entity_id") or body["id"])


async def _author(author: Actor, repository: uuid.UUID) -> dict[str, str]:
    """A small repository, written through the routes any tenant uses."""
    r = f"/tenants/{repository}"
    ids: dict[str, str] = {}
    ids["Abilities"] = _id(await author.post(f"{r}/stat-groups", json={"name": "Abilities"}))
    ids["Strength"] = _id(
        await author.post(
            f"{r}/stat-definitions",
            json={"name": "Strength", "stat_group_id": ids["Abilities"], "value_type": "int"},
        )
    )
    ids["Sword"] = _id(await author.post(f"{r}/items", json={"name": "Sword"}))
    ids["Longsword"] = _id(
        await author.post(f"{r}/items", json={"name": "Longsword", "prototype_ids": [ids["Sword"]]})
    )
    set_stat = await author.put(
        f"{r}/entities/{ids['Longsword']}/stats/{ids['Strength']}", json={"value": 10}
    )
    assert set_stat.status_code == 200, set_stat.text
    ids["Elminster"] = _id(await author.post(f"{r}/characters", json={"name": "Elminster"}))
    ids["Harpers"] = _id(
        await author.post(
            f"{r}/groups", json={"name": "Harpers", "member_character_ids": [ids["Elminster"]]}
        )
    )
    info = await author.post(
        f"{r}/entities/{ids['Longsword']}/information",
        json={
            "title": "Longsword",
            "type": "description",
            "is_public": True,
            "content": "Carried by [[elminster]].",
            "locale": "en",
        },
    )
    assert info.status_code == 201, info.text
    return ids


async def _names(tenant_id: uuid.UUID) -> list[str]:
    async with admin_session_factory() as session:
        return sorted(
            await session.scalars(select(Entity.name).where(Entity.tenant_id == tenant_id))
        )


async def test_authoring_contributions_and_dry_runs(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await author.create_tenant("Armoury", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        ids = await _author(author, repository)
        await author.put(f"/tenants/{repository}/subscribers/{table}")
        await author.put(f"/tenants/{repository}/published")
        url = f"/tenants/{table}/repositories/{repository}"

        # A dry run does it all and keeps nothing.
        dry = await gm.post(f"{url}/copy", json={"dry_run": True})
        assert dry.status_code == 200, dry.text
        assert dry.json()["dry_run"] is True
        assert dry.json()["steps"][0]["entities"] == 4
        assert await _names(table) == []
        listed = (await gm.get(f"/tenants/{table}/repositories")).json()["items"]
        assert listed[0]["copied_at"] is None

        copied = await gm.post(f"{url}/copy")
        assert copied.status_code == 201, copied.text
        assert copied.json()["dry_run"] is False
        assert await _names(table) == ["Elminster", "Harpers", "Longsword", "Sword"]

        # What it contributed: counts in the listing, rows on their own.
        (entry,) = (await gm.get(f"/tenants/{table}/repositories")).json()["items"]
        assert entry["contributed"] == {
            "entities": 4,
            "stat_groups_copied": 1,
            "stat_groups_merged": 0,
            "stat_definitions_copied": 1,
            "stat_definitions_merged": 0,
        }
        rows = (await gm.get(f"{url}/contributions", params={"kind": "entity"})).json()["items"]
        assert sorted(r["name"] for r in rows) == ["Elminster", "Harpers", "Longsword", "Sword"]
        assert {r["source_id"] for r in rows} == {
            ids["Elminster"],
            ids["Harpers"],
            ids["Longsword"],
            ids["Sword"],
        }

        # The copy stays listed, and its contributions readable, without
        # the grant.
        await gm.delete(f"/tenants/{table}/repositories/{repository}")
        (entry,) = (await gm.get(f"/tenants/{table}/repositories")).json()["items"]
        assert (entry["granted_at"], entry["contributed"]["entities"]) == (None, 4)
        assert (await gm.get(f"{url}/contributions")).json()["total"] == 6

        never = await gm.get(f"/tenants/{table}/repositories/{uuid.uuid4()}/contributions")
        assert never.status_code == 409
        assert never.json()["type"] == "repository-not-copied"

        # An update's dry run applies nothing.
        await author.put(f"/tenants/{repository}/subscribers/{table}")
        renamed = await author.patch(
            f"/tenants/{repository}/items/{ids['Sword']}", json={"name": "Blade"}
        )
        assert renamed.status_code == 200, renamed.text
        action = {"kind": "entity", "source_id": ids["Sword"], "action": "apply"}
        dry_update = await gm.post(f"{url}/updates", json={"actions": [action], "dry_run": True})
        assert dry_update.status_code == 200, dry_update.text
        assert (dry_update.json()["dry_run"], dry_update.json()["applied"]) == (True, 1)
        assert "Sword" in await _names(table)
        applied = await gm.post(f"{url}/updates", json={"actions": [action]})
        assert applied.json()["dry_run"] is False
        assert "Blade" in await _names(table)
    finally:
        await cleanup([table, repository], [author, gm])


async def test_copying_again(raw_client: AsyncClient, fake_jwks_server: FakeJwksServer) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await author.create_tenant("Armoury", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        await _author(author, repository)
        await author.put(f"/tenants/{repository}/subscribers/{table}")
        await author.put(f"/tenants/{repository}/published")
        url = f"/tenants/{table}/repositories/{repository}"
        assert (await gm.post(f"{url}/copy")).status_code == 201

        # The table builds on the copy: its own entity inheriting from the
        # copied Longsword, its own stat in the copied group, a value set
        # with the copied Strength.
        local = {
            r["name"]: r["local_id"] for r in (await gm.get(f"{url}/contributions")).json()["items"]
        }
        t = f"/tenants/{table}"
        heirloom = _id(
            await gm.post(
                f"{t}/items", json={"name": "Heirloom", "prototype_ids": [local["Longsword"]]}
            )
        )
        honor = await gm.post(
            f"{t}/stat-definitions",
            json={"name": "Honor", "stat_group_id": local["Abilities"], "value_type": "int"},
        )
        assert honor.status_code == 201, honor.text
        set_stat = await gm.put(
            f"{t}/entities/{heirloom}/stats/{local['Strength']}", json={"value": 3}
        )
        assert set_stat.status_code == 200, set_stat.text

        assert (await gm.post(f"{url}/copy")).json()["type"] == "repository-already-copied"

        # A purge, tried first: it names what of the table's own would go.
        dry = await gm.post(f"{url}/copy", json={"again": "purge", "dry_run": True})
        assert dry.status_code == 200, dry.text
        previous = dry.json()["previous"]
        assert (previous["mode"], previous["entities"]) == ("purge", 4)
        assert previous["also_removed"] == {
            "stat_definition": 1,
            "entity_stat": 1,
            "entity_prototype": 1,
        }
        assert "Heirloom" in await _names(table)
        assert len(await _names(table)) == 5

        purged = await gm.post(f"{url}/copy", json={"again": "purge"})
        assert purged.status_code == 201, purged.text
        assert await _names(table) == ["Elminster", "Harpers", "Heirloom", "Longsword", "Sword"]
        async with admin_session_factory() as session:
            definitions = sorted(
                await session.scalars(
                    select(StatDefinition.name).where(StatDefinition.tenant_id == table)
                )
            )
            heirloom_stats = await session.scalar(
                select(func.count())
                .select_from(EntityStat)
                .where(EntityStat.entity_id == uuid.UUID(heirloom))
            )
        assert (definitions, heirloom_stats) == (["Strength"], 0)
        heirloom_now = (await gm.get(f"{t}/entities/{heirloom}")).json()
        assert heirloom_now["prototypes"] == []

        # Keep: the old copy stays as the table's own, the new one sits
        # beside it, and the collisions need choices.
        plan = (await gm.get(f"{url}/copy-plan")).json()
        assert plan["steps"][0]["already_copied"] is True
        refused = await gm.post(f"{url}/copy", json={"again": "keep"})
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-copy-needs-choices"
        merges = [
            {"kind": c["kind"], "source_id": c["source_id"], "action": "merge"}
            for c in refused.json()["collisions"]
        ]
        kept = await gm.post(f"{url}/copy", json={"again": "keep", "resolutions": merges})
        assert kept.status_code == 201, kept.text
        assert kept.json()["previous"]["mode"] == "keep"
        names = await _names(table)
        assert names.count("Longsword") == 2 and "Heirloom" in names
        rows = (await gm.get(f"{url}/contributions", params={"kind": "entity"})).json()
        assert rows["total"] == 4  # only the new copy is linked

        async with admin_session_factory() as session:
            actions = set(
                await session.scalars(select(AuditLog.action).where(AuditLog.tenant_id == table))
            )
        assert {"repository.copy_purged", "repository.copy_forgotten"} <= actions
    finally:
        await cleanup([table, repository], [author, gm])
