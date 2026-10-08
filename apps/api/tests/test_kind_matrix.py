"""The round-trip matrix (ADR 0217, RFC 0041 section 2): every combination of kinds a repository may
be published with goes through a first copy, an update that adds the entry, an update that changes
its name, parents and stats, a kind added and removed after the copy, and a purge - in a plain
repository and in a bridge (RFC 0033).

Publishing checks `PUBLISHABLE_KIND_COMBINATIONS`, and this file holds that list complete: a
combination is added there together with its row here, and a row here is not a combination until it
is added there. A draft may hold any combination; what is not on the list is not published.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import func, select

from lorenzo_api.entity_kinds import PUBLISHABLE_KIND_COMBINATIONS
from lorenzo_api.models import (
    Being,
    Character,
    Entity,
    EntityPrototype,
    EntityStat,
    Information,
    Item,
    ItemInstance,
    Payload,
    PayloadDescription,
    RepositoryCopyLinkEntity,
    StatDefinition,
    StatGroup,
    StatValueType,
)

# Each combination of kinds, as the snapshot writes it, and the kind a repository's author adds
# and then removes after the copy: none where no route can (an inventory item never takes `item`
# and a being that is a character never loses `being`; both are made and unmade in the library,
# not by an update).
MATRIX: dict[tuple[str, ...], str | None] = {
    (): "item",
    ("item",): "being",
    ("being",): "item",
    ("being", "item"): "being",
    ("item_instance",): None,
    ("being", "character"): None,
}
_ORDER = ["item", "item_instance", "being", "character"]


def test_the_matrix_holds_exactly_the_combinations_publishing_allows() -> None:
    assert set(MATRIX) == PUBLISHABLE_KIND_COMBINATIONS


def _expected(kinds: tuple[str, ...]) -> list[str]:
    return [k for k in _ORDER if k in kinds]


@dataclass
class _Scene:
    author: Actor
    gm: Actor
    repository: uuid.UUID
    table: uuid.UUID
    bridge: uuid.UUID | None
    weight: uuid.UUID
    ids: dict[str, uuid.UUID]
    tenants: list[uuid.UUID]

    async def publish(self, repository: uuid.UUID | None = None) -> None:
        response = await self.author.put(
            f"/tenants/{repository or self.repository}/published",
            json={"acknowledge_breaking": True},
        )
        assert response.status_code == 200, response.text

    async def updates(self) -> dict[str, Any]:
        response = await self.gm.get(
            f"/tenants/{self.table}/repositories/{self.repository}/updates"
        )
        assert response.status_code == 200, response.text
        return response.json()  # type: ignore[no-any-return]

    async def apply(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        response = await self.gm.post(
            f"/tenants/{self.table}/repositories/{self.repository}/updates",
            json={"actions": [{"confirm": True, **a} for a in actions]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["not_applied"] == [], response.json()["not_applied"]
        return response.json()  # type: ignore[no-any-return]

    async def library_entry(self, name: str) -> dict[str, Any]:
        """The library's entry of that name, as its GM reads it."""
        async with admin_session_factory() as session:
            entity_id = (
                await session.scalars(
                    select(Entity.id).where(Entity.tenant_id == self.table, Entity.name == name)
                )
            ).one()
        response = await self.gm.get(f"/tenants/{self.table}/entities/{entity_id}")
        assert response.status_code == 200, response.text
        return response.json()  # type: ignore[no-any-return]

    async def library_names(self) -> set[str]:
        async with admin_session_factory() as session:
            return set(
                await session.scalars(select(Entity.name).where(Entity.tenant_id == self.table))
            )


async def _make(
    scene_author: Actor,
    repository: uuid.UUID,
    name: str,
    kinds: tuple[str, ...],
    parents: list[uuid.UUID],
) -> uuid.UUID:
    """An entry of those kinds in a repository: through the route where one exists, and straight
    in the database for an inventory item and a character, which no route makes this way."""
    if set(kinds) <= {"item", "being"}:
        response = await scene_author.post(
            f"/tenants/{repository}/entities",
            json={"name": name, "kinds": list(kinds), "parents": [str(p) for p in parents]},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["id"])
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=repository, name=name)
        session.add(entity)
        await session.flush()
        if "item_instance" in kinds:
            session.add(ItemInstance(entity_id=entity.id, tenant_id=repository))
        if "being" in kinds:
            session.add(Being(entity_id=entity.id, tenant_id=repository))
            await session.flush()
        if "character" in kinds:
            session.add(Character(entity_id=entity.id, tenant_id=repository))
        for parent in parents:
            session.add(
                EntityPrototype(entity_id=entity.id, prototype_id=parent, tenant_id=repository)
            )
        await session.commit()
        return entity.id


async def _describe(repository: uuid.UUID, entity_id: uuid.UUID, text: str) -> None:
    async with admin_session_factory() as session:
        info = Information(
            tenant_id=repository,
            entity_id=entity_id,
            title="Lore",
            type="description",
            is_public=True,
        )
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=repository, information_id=info.id, order=0)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=payload.id, tenant_id=repository, locale="en-US", content=text
            )
        )
        await session.commit()


async def _stat(repository: uuid.UUID, entity_id: uuid.UUID, weight: uuid.UUID, value: int) -> None:
    async with admin_session_factory() as session:
        row = await session.get(EntityStat, (entity_id, weight))
        if row is None:
            session.add(
                EntityStat(
                    entity_id=entity_id,
                    stat_definition_id=weight,
                    tenant_id=repository,
                    value_int=value,
                )
            )
        else:
            row.value_int = value
        await session.commit()


async def _share(author: Actor, repository: uuid.UUID, *libraries: uuid.UUID) -> None:
    for library in libraries:
        response = await author.put(f"/tenants/{repository}/subscribers/{library}")
        assert response.status_code in (200, 201), response.text


async def _scene(
    raw_client: AsyncClient, jwks: FakeJwksServer, kinds: tuple[str, ...], *, bridge: bool
) -> _Scene:
    """Armoury, with a stat (Weight), a bare parent (Base) and Alpha, the entry under test: of
    `kinds`, with Base as its parent, a Weight of 5, a link name and a note. Published, and
    copied by a library, directly or - in a bridge - through a bridge that copied it, added a
    parent of its own to Alpha, and was published and copied in turn."""
    author = await make_actor(raw_client, jwks, "author")
    gm = await make_actor(raw_client, jwks, "gm")
    repository = await author.create_tenant("Armoury", kind="repository")
    table = await gm.create_tenant("My Table")
    tenants = [table, repository]
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=repository, name="Body")
        session.add(group)
        await session.flush()
        weight = StatDefinition(
            tenant_id=repository,
            stat_group_id=group.id,
            name="Weight",
            value_type=StatValueType.INT,
        )
        session.add(weight)
        await session.commit()
        weight_id = weight.id
    base = await _make(author, repository, "Base", (), [])
    alpha = await _make(author, repository, "Alpha", kinds, [base])
    await _stat(repository, alpha, weight_id, 5)
    await _describe(repository, alpha, "An old thing.")
    scene = _Scene(
        author, gm, repository, table, None, weight_id, {"Base": base, "Alpha": alpha}, tenants
    )
    await _share(author, repository, table)
    await scene.publish()
    if not bridge:
        copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy", json={})
        assert copied.status_code == 201, copied.text
        return scene

    bridge_id = await author.create_tenant("Armoury 5e", kind="repository")
    tenants.append(bridge_id)
    scene.bridge = bridge_id
    await _share(author, repository, bridge_id)
    taken = await author.post(f"/tenants/{bridge_id}/repositories/{repository}/copy", json={})
    assert taken.status_code == 201, taken.text
    async with admin_session_factory() as session:
        copy_of_alpha = (
            await session.scalars(
                select(Entity.id).where(Entity.tenant_id == bridge_id, Entity.name == "Alpha")
            )
        ).one()
        silvered = Entity(tenant_id=bridge_id, name="Silvered")
        session.add(silvered)
        await session.flush()
        session.add(Item(entity_id=silvered.id, tenant_id=bridge_id))
        session.add(
            EntityPrototype(entity_id=copy_of_alpha, prototype_id=silvered.id, tenant_id=bridge_id)
        )
        await session.commit()
    await _share(author, bridge_id, table)
    await scene.publish(bridge_id)
    copied = await gm.post(f"/tenants/{table}/repositories/{bridge_id}/copy", json={})
    assert copied.status_code == 201, copied.text
    return scene


async def _marker_counts(tenant_id: uuid.UUID) -> dict[str, int]:
    async with admin_session_factory() as session:
        return {
            kind: (
                await session.scalar(
                    select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
                )
            )
            or 0
            for kind, model in (
                ("item", Item),
                ("item_instance", ItemInstance),
                ("being", Being),
                ("character", Character),
            )
        }


@pytest.mark.parametrize("bridge", [False, True], ids=["plain", "bridge"])
@pytest.mark.parametrize("kinds", sorted(MATRIX), ids=lambda k: "+".join(k) or "bare")
async def test_a_combination_of_kinds_survives_copy_update_and_purge(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    kinds: tuple[str, ...],
    bridge: bool,
) -> None:
    scene = await _scene(raw_client, fake_jwks_server, kinds, bridge=bridge)
    author, repository, ids = scene.author, scene.repository, scene.ids
    try:
        # 1. The first copy: the same kinds, the parent, the stat, the note and the link.
        alpha = await scene.library_entry("Alpha")
        base = await scene.library_entry("Base")
        assert alpha["kinds"] == _expected(kinds)
        assert [p["id"] for p in alpha["prototypes"] if p["name"] == "Base"] == [base["id"]]
        assert [(s["name"], s["value"], s["own"]) for s in alpha["stats"]] == [("Weight", 5, True)]
        assert [(i["title"]) for i in alpha["information"]] == ["Lore"]
        if bridge:
            assert {p["name"] for p in alpha["prototypes"]} == {"Base", "Silvered"}

        # 2. An update that adds the entry.
        beta = await _make(author, repository, "Beta", kinds, [ids["Base"]])
        await scene.publish()
        found = await scene.updates()
        assert [(a["kind"], a["name"]) for a in found["added"]] == [("entity", "Beta")]
        await scene.apply([{"kind": "entity", "source_id": str(beta), "action": "add"}])
        assert (await scene.library_entry("Beta"))["kinds"] == _expected(kinds)
        assert (await scene.updates())["added"] == []

        # 3. An update that changes the name, the parents and the stats; a note changed upstream
        # is not carried by an update, so the library's stays as it was copied.
        gamma = await _make(author, repository, "Base Two", (), [])
        async with admin_session_factory() as session:
            entity = await session.get_one(Entity, ids["Alpha"])
            entity.name = "Alpha Renamed"
            await session.execute(
                EntityPrototype.__table__.delete().where(
                    EntityPrototype.entity_id == ids["Alpha"],
                    EntityPrototype.prototype_id == ids["Base"],
                )
            )
            session.add(
                EntityPrototype(entity_id=ids["Alpha"], prototype_id=gamma, tenant_id=repository)
            )
            await session.commit()
        await _stat(repository, ids["Alpha"], scene.weight, 9)
        async with admin_session_factory() as session:
            for payload in await session.scalars(
                select(PayloadDescription).where(PayloadDescription.tenant_id == repository)
            ):
                payload.content = "A new thing."
            await session.commit()
        await scene.publish()
        found = await scene.updates()
        fields = {
            f["field"] for row in found["changed"] if row["name"] == "Alpha" for f in row["fields"]
        }
        assert fields == {"name", "prototypes", f"stats:{scene.weight}"}
        await scene.apply(
            [
                {"kind": "entity", "source_id": str(gamma), "action": "add"},
                {"kind": "entity", "source_id": str(ids["Alpha"]), "action": "apply"},
            ]
        )
        renamed = await scene.library_entry("Alpha Renamed")
        assert renamed["kinds"] == _expected(kinds)
        assert [(s["name"], s["value"]) for s in renamed["stats"]] == [("Weight", 9)]
        assert "Base Two" in {p["name"] for p in renamed["prototypes"]}
        assert "Base" not in {p["name"] for p in renamed["prototypes"]}
        if bridge:
            assert "Silvered" in {p["name"] for p in renamed["prototypes"]}
        assert [i["title"] for i in renamed["information"]] == ["Lore"]

        # 4. A kind added and removed after the copy, where a route can.
        extra = MATRIX[kinds]
        if extra is not None:
            # Taken away first where the entry has it, added first where it has not; then back.
            for verb in ("delete", "put") if extra in kinds else ("put", "delete"):
                response = await getattr(author, verb)(
                    f"/tenants/{repository}/entities/{ids['Alpha']}/kinds/{extra}"
                )
                assert response.status_code in (200, 201), response.text
                expected = _expected(
                    tuple({*kinds, extra} if verb == "put" else set(kinds) - {extra})
                )
                assert response.json()["kinds"] == expected
                await scene.publish()
                await scene.apply(
                    [{"kind": "entity", "source_id": str(ids["Alpha"]), "action": "apply"}]
                )
                assert (await scene.library_entry("Alpha Renamed"))["kinds"] == expected
                assert [row["name"] for row in (await scene.updates())["changed"]] == []

        # 5. A purge: copying again deletes what the first copy made, and the copy that replaces
        # it is the repository's now, with nothing of the old one left behind.
        before = await scene.library_names()
        again = await scene.gm.post(
            f"/tenants/{scene.table}/repositories/{repository}/copy",
            json={"again": "purge"},
        )
        assert again.status_code == 201, again.text
        assert again.json()["previous"]["mode"] == "purge"
        assert await scene.library_names() == before
        assert (await scene.library_entry("Alpha Renamed"))["kinds"] == _expected(kinds)
        async with admin_session_factory() as session:
            repo_entities = await session.scalar(
                select(func.count()).select_from(Entity).where(Entity.tenant_id == repository)
            )
            copied = await session.scalar(
                select(func.count())
                .select_from(RepositoryCopyLinkEntity)
                .where(
                    RepositoryCopyLinkEntity.tenant_id == scene.table,
                    RepositoryCopyLinkEntity.source_tenant_id == repository,
                    RepositoryCopyLinkEntity.entity_id.is_not(None),
                )
            )
        assert copied == repo_entities
        # No marker row of the old copy is left over: the library holds as many of each kind as
        # the repository does (and, in a bridge, the bridge's own item).
        mine, theirs = await _marker_counts(scene.table), await _marker_counts(repository)
        silvered = 1 if bridge else 0
        assert mine["item"] == theirs["item"] + silvered
        for kind in ("item_instance", "being", "character"):
            assert mine[kind] == theirs[kind], kind
        if bridge:
            # The copy the bridge attached to went with the purge, so its parent did too, and the
            # library is shown it as an attachment it took and no longer has (ADR 0172).
            shown = (
                await scene.gm.get(f"/tenants/{scene.table}/repositories/{scene.bridge}/updates")
            ).json()
            assert [
                (a["child_name"], a["parent_name"]) for a in shown["attachments_deleted_locally"]
            ] == [("Alpha Renamed", "Silvered")], shown
    finally:
        await cleanup(scene.tenants, [scene.author, scene.gm])
