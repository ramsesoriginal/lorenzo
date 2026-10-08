"""ADR 0208 through the real HTTP API: a release holds the digest of the rows the update
engine compares, the author's preview says what a publish would release before it is made,
and what the preview says is what the publish records.
"""

import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from httpx import AsyncClient
from sqlalchemy import delete, func, select, text, update

from lorenzo_api.db import engine
from lorenzo_api.models import (
    Character,
    ComputedStatLinear,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    Information,
    Item,
    Payload,
    PayloadDescription,
    RepositoryCopy,
    RepositoryRelease,
    RepositoryReleasedRow,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
)

# --- Editing a repository, one kind of change at a time ----------------------------------

Edit = Callable[[ReleaseWorld], Awaitable[None]]


async def _rename(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        (await session.get_one(Entity, w.ids["Longsword"])).name = "Long Sword"
        await session.commit()


async def _stat_value(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        stat = await session.get_one(EntityStat, (w.ids["Longsword"], w.ids["Strength"]))
        stat.value_int = 11
        await session.commit()


async def _formula(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        formula = await session.get_one(ComputedStatLinear, (w.ids["Longsword"], w.ids["Damage"]))
        formula.multiplier = Decimal("0.75")
        await session.commit()


async def _prototype(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            delete(EntityPrototype).where(EntityPrototype.entity_id == w.ids["Dagger"])
        )
        await session.commit()


async def _stat_group_membership(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        session.add(
            EntityStatGroup(
                entity_id=w.ids["Dagger"], stat_group_id=w.ids["Abilities"], tenant_id=w.repository
            )
        )
        await session.commit()


async def _enum_value_added(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        session.add(
            StatDefinitionEnumValue(
                tenant_id=w.repository, stat_definition_id=w.ids["Mood"], value="furious"
            )
        )
        await session.commit()


async def _slug(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        slug = await session.get_one(EntitySlug, w.ids["Longsword"])
        slug.slug = "long-sword"
        await session.commit()


async def _kind(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        session.add(Character(entity_id=w.ids["Orc"], tenant_id=w.repository))
        await session.commit()


async def _group_priority(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        (await session.get_one(StatGroup, w.ids["Extras"])).priority = 5
        await session.commit()


async def _value_type(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        # Nothing holds a value for Speed, so its type can change.
        await session.execute(
            update(StatDefinition)
            .where(StatDefinition.id == w.ids["Speed"])
            .values(value_type=StatValueType.TEXT)
        )
        await session.commit()


async def _added(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        blade = Entity(tenant_id=w.repository, name="Blade")
        session.add(blade)
        await session.flush()
        session.add(Item(entity_id=blade.id, tenant_id=w.repository))
        await session.commit()


async def _removed(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        await session.execute(delete(Entity).where(Entity.id == w.ids["Orc"]))
        await session.commit()


# What each edit does to the preview: (kind, bucket) of the one row it touches, and its name
# afterwards (or before, for a removal).
EDITS: dict[str, tuple[Edit, str, str, str]] = {
    "name": (_rename, "changed", "entity", "Long Sword"),
    "stat value": (_stat_value, "changed", "entity", "Longsword"),
    "formula": (_formula, "changed", "entity", "Longsword"),
    "prototype": (_prototype, "changed", "entity", "Dagger"),
    "stat group membership": (_stat_group_membership, "changed", "entity", "Dagger"),
    "enum value": (_enum_value_added, "changed", "stat_definition", "Mood"),
    "slug": (_slug, "changed", "entity", "Longsword"),
    "kind of the entry": (_kind, "changed", "entity", "Orc"),
    "stat group": (_group_priority, "changed", "stat_group", "Extras"),
    "type of a stat value": (_value_type, "changed", "stat_definition", "Speed"),
    "added": (_added, "added", "entity", "Blade"),
    "removal": (_removed, "removed", "entity", "Orc"),
}


@pytest.mark.parametrize("what", sorted(EDITS))
async def test_a_release_matches_until_the_content_changes_and_then_says_how(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, what: str
) -> None:
    edit, bucket, kind, name = EDITS[what]
    w = await release_world(raw_client, fake_jwks_server)
    try:
        release = (await w.releases())[0]
        assert release["digest"]

        # Two loads of unchanged content agree with each other and with the release.
        first, second = await w.preview(), await w.preview()
        assert first["live_digest"] == second["live_digest"] == release["digest"]
        assert first["matches"] is True
        assert first["differing_rows"] == 0
        assert first["added"] == first["changed"] == first["removed"] == []

        await edit(w)

        after = await w.preview()
        assert after["matches"] is False
        assert after["live_digest"] != release["digest"]
        assert after["differing_rows"] == 1
        assert [(r["kind"], r["name"]) for r in after[bucket]] == [(kind, name)]
        assert sum(len(after[b]) for b in ("added", "changed", "removed")) == 1
        # The release it is compared with did not move.
        assert after["release"]["id"] == release["id"]

        # Publishing again makes the new content the one that is matched.
        if what in ("slug", "removal", "enum value", "kind of the entry", "type of a stat value"):
            # Some of these are breaking, which a publish refuses until it is acknowledged.
            published = await w.publish(acknowledge_breaking=True)
        else:
            published = await w.publish()
        assert published["digest"] not in (None, release["digest"])
        again = await w.preview()
        assert again["matches"] is True and again["differing_rows"] == 0
        assert again["live_digest"] == published["digest"]
    finally:
        await w.done()


async def test_a_text_edit_is_not_tracked_and_is_hinted(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    try:
        before = await w.preview()
        assert before["descriptions_edited"] == 0
        async with admin_session_factory() as session:
            info = Information(
                tenant_id=w.repository,
                entity_id=w.ids["Longsword"],
                title="Lore",
                type="description",
                is_public=True,
            )
            session.add(info)
            await session.flush()
            payload = Payload(tenant_id=w.repository, information_id=info.id)
            session.add(payload)
            await session.flush()
            session.add(
                PayloadDescription(
                    payload_id=payload.id, tenant_id=w.repository, locale="en", content="Sharp."
                )
            )
            await session.commit()
            payload_id = payload.id

        after = await w.preview()
        # The digest does not see it, and says so; the hint counts it.
        assert after["matches"] is True
        assert after["differing_rows"] == 0
        assert after["descriptions_edited"] == 1

        # Editing the same description again is still one description.
        async with admin_session_factory() as session:
            (await session.get_one(Payload, payload_id)).updated_at = func.now()
            await session.commit()
        assert (await w.preview())["descriptions_edited"] == 1

        # The release records the hint, and the next one starts from zero.
        release = await w.publish(label="1.1")
        assert release["counts"]["descriptions_edited"] == 1
        assert (await w.preview())["descriptions_edited"] == 0
    finally:
        await w.done()


# --- What a release records ---------------------------------------------------------------


async def test_the_first_release_counts_everything_as_added_and_has_no_breaking_rows(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        preview = await w.preview()
        assert preview["release"] is None
        assert preview["matches"] is None
        assert preview["baseline"] is False
        assert preview["breaking"] == []
        assert preview["libraries_told"] == 1
        # Two groups, four stats, three entries; nothing to be edited or removed.
        assert preview["counts"]["stat_groups"] == {"added": 2, "changed": 0, "removed": 0}
        assert preview["counts"]["stat_definitions"] == {"added": 4, "changed": 0, "removed": 0}
        assert preview["counts"]["entities"] == {"added": 3, "changed": 0, "removed": 0}
        assert preview["counts"]["attachments"] == {"added": 0, "removed": 0}

        release = await w.publish(label="1.0")
        assert release["counts"] == preview["counts"]
        assert release["breaking_rows"] == []
        assert release["breaking"] is False
        assert release["digest"] == preview["live_digest"]
        # Listed too, as any member of the repository reads it.
        assert (await w.releases())[0]["counts"] == release["counts"]
    finally:
        await w.done()


async def test_a_release_counts_what_it_added_changed_and_removed(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    try:
        for edit in (_rename, _stat_value, _group_priority, _added, _removed):
            await edit(w)
        preview = await w.preview()
        assert preview["counts"]["entities"] == {"added": 1, "changed": 1, "removed": 1}
        assert preview["counts"]["stat_groups"] == {"added": 0, "changed": 1, "removed": 0}
        assert preview["differing_rows"] == 4
        assert [r["name"] for r in preview["added"]] == ["Blade"]
        assert [r["name"] for r in preview["changed"]] == ["Extras", "Long Sword"]
        assert [(r["kind"], r["name"]) for r in preview["removed"]] == [("entity", "Orc")]

        # Removing an entry is breaking: the preview says so, and so does the publish.
        assert [(b["reason"], b["name"]) for b in preview["breaking"]] == [
            ("entity_removed", "Orc")
        ]
        refused = await w.author.put(f"/tenants/{w.repository}/published", json={})
        assert refused.status_code == 409
        assert refused.json()["type"] == "release-has-breaking-changes"
        release = await w.publish(acknowledge_breaking=True, label="2.0")
        assert release["counts"] == preview["counts"]
        assert release["breaking"] is True
        assert [(b["kind"], b["reason"], b["name"]) for b in release["breaking_rows"]] == [
            ("entity", "entity_removed", "Orc")
        ]
        # What was published is one set of rows, not one for each release.
        async with admin_session_factory() as session:
            stored = await session.scalar(
                select(func.count())
                .select_from(RepositoryReleasedRow)
                .where(RepositoryReleasedRow.tenant_id == w.repository)
            )
        assert stored == 2 + 4 + 3  # groups, stats, entries now
    finally:
        await w.done()


async def test_the_preview_names_at_most_two_hundred_rows_and_counts_all(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    try:
        async with admin_session_factory() as session:
            session.add_all(
                Entity(tenant_id=w.repository, name=f"Arrow {n:03}") for n in range(230)
            )
            await session.commit()
        preview = await w.preview()
        assert preview["counts"]["entities"]["added"] == 230
        assert len(preview["added"]) == 200
        assert preview["differing_rows"] == 230
    finally:
        await w.done()


# --- The detector -------------------------------------------------------------------------


async def _remove_definition(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        await session.execute(delete(StatDefinition).where(StatDefinition.id == w.ids["Speed"]))
        await session.commit()


async def _remove_group(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        await session.execute(delete(StatGroup).where(StatGroup.id == w.ids["Extras"]))
        await session.commit()


async def _remove_enum_value(w: ReleaseWorld) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            delete(StatDefinitionEnumValue).where(
                StatDefinitionEnumValue.stat_definition_id == w.ids["Mood"],
                StatDefinitionEnumValue.value == "angry",
            )
        )
        await session.commit()


# (what, edit, reason, kind, name, a word the explanation must have)
HITS: list[tuple[str, Edit, str, str, str, str]] = [
    ("a removed entry", _removed, "entity_removed", "entity", "Orc", "detached"),
    (
        "a removed stat",
        _remove_definition,
        "stat_definition_removed",
        "stat_definition",
        "Speed",
        "was removed",
    ),
    (
        "a retyped stat",
        _value_type,
        "stat_definition_retyped",
        "stat_definition",
        "Speed",
        "int to text",
    ),
    (
        "a removed stat group",
        _remove_group,
        "stat_group_removed",
        "stat_group",
        "Extras",
        "was removed",
    ),
    (
        "a removed enum value",
        _remove_enum_value,
        "enum_value_removed",
        "stat_definition",
        "Mood",
        "angry",
    ),
    ("a kind change", _kind, "kinds_changed", "entity", "Orc", "being to being, character"),
    ("a changed link name", _slug, "slug_changed", "entity", "Longsword", "long-sword"),
]


@pytest.mark.parametrize("hit", HITS, ids=[h[0] for h in HITS])
async def test_a_publish_with_a_breaking_change_is_refused_until_it_is_acknowledged(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    hit: tuple[str, Edit, str, str, str, str],
) -> None:
    _, edit, reason, kind, name, word = hit
    w = await release_world(raw_client, fake_jwks_server)
    try:
        await edit(w)
        preview = await w.preview()
        assert [(b["kind"], b["reason"], b["name"]) for b in preview["breaking"]] == [
            (kind, reason, name)
        ]
        assert word in preview["breaking"][0]["detail"]

        refused = await w.author.put(f"/tenants/{w.repository}/published", json={"label": "2.0"})
        assert refused.status_code == 409, refused.text
        problem = refused.json()
        assert problem["type"] == "release-has-breaking-changes"
        assert [(b["kind"], b["reason"], b["name"]) for b in problem["breaking_rows"]] == [
            (kind, reason, name)
        ]
        # Nothing was made: no release, and the content still matches the one before.
        assert [r["label"] for r in await w.releases()] == ["1.0"]
        assert (await w.preview())["release"]["label"] == "1.0"

        release = await w.publish(label="2.0", acknowledge_breaking=True)
        assert release["breaking"] is True
        assert [(b["kind"], b["reason"], b["name"]) for b in release["breaking_rows"]] == [
            (kind, reason, name)
        ]
        # Kept on the release, for good.
        listed = {r["label"]: r for r in await w.releases()}
        assert listed["2.0"]["breaking_rows"] == release["breaking_rows"]
        assert listed["1.0"]["breaking_rows"] == []
    finally:
        await w.done()


async def test_changes_that_break_nothing_publish_without_acknowledging(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    try:
        for edit in (_rename, _stat_value, _formula, _enum_value_added, _added, _group_priority):
            await edit(w)
        assert (await w.preview())["breaking"] == []
        release = await w.publish(label="1.1")
        assert release["breaking"] is False
        assert release["breaking_rows"] == []
    finally:
        await w.done()


async def test_an_author_may_call_a_release_breaking_when_the_detector_found_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    try:
        release = await w.publish(label="1.1", breaking=True)
        assert release["breaking"] is True
        assert release["breaking_rows"] == []
    finally:
        await w.done()


async def test_acknowledging_costs_nothing_when_there_is_nothing_to_acknowledge(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    try:
        release = await w.publish(label="1.1", acknowledge_breaking=True)
        assert release["breaking"] is False
    finally:
        await w.done()


async def test_a_repository_published_before_digests_is_compared_with_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A release made before there was a digest (ADR 0207) has none to compare with: the
    next publish is a baseline, whatever was removed, and the marks stay null until then."""
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        async with admin_session_factory() as session:
            await session.execute(
                update(RepositoryRelease)
                .where(RepositoryRelease.tenant_id == w.repository)
                .values(digest=None, counts=None)
            )
            await session.commit()
        await _removed(w)
        preview = await w.preview()
        assert preview["baseline"] is False
        assert preview["matches"] is None
        assert preview["breaking"] == []
        updates = await w.updates()
        assert updates["release"]["label"] == "1.0"
        assert all(r["state"] is None for r in updates["removed"])
        release = await w.publish(label="1.1")
        assert release["breaking"] is False
        # From here on there is a baseline.
        assert (await w.preview())["matches"] is True
    finally:
        await w.done()


# --- Attachments --------------------------------------------------------------------------


async def test_an_attachment_added_after_a_release_is_a_warning_and_not_a_breaking_change(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, published=True)
    bridge = await w.author.create_tenant("Armoury Plus", kind="repository")
    w.tenants.append(bridge)
    try:
        assert (
            await w.author.put(f"/tenants/{w.repository}/subscribers/{bridge}")
        ).status_code == 201
        copied = await w.author.post(f"/tenants/{bridge}/repositories/{w.repository}/copy", json={})
        assert copied.status_code == 201, copied.text
        async with admin_session_factory() as session:
            own = Entity(tenant_id=bridge, name="Silvered")
            session.add(own)
            await session.flush()
            session.add(Item(entity_id=own.id, tenant_id=bridge))
            await session.commit()
            copy_of_dagger = await session.scalar(
                select(Entity.id).where(Entity.tenant_id == bridge, Entity.name == "Dagger")
            )
        first = await w.author.put(f"/tenants/{bridge}/published", json={"label": "1"})
        assert first.status_code == 200, first.text
        assert first.json()["release"]["counts"]["attachments"] == {"added": 0, "removed": 0}

        async with admin_session_factory() as session:
            silvered = await session.scalar(
                select(Entity.id).where(Entity.tenant_id == bridge, Entity.name == "Silvered")
            )
            session.add(
                EntityPrototype(entity_id=copy_of_dagger, prototype_id=silvered, tenant_id=bridge)
            )
            await session.commit()

        preview = (await w.author.get(f"/tenants/{bridge}/release-preview")).json()
        assert preview["counts"]["attachments"] == {"added": 1, "removed": 0}
        assert [(r["kind"], r["name"], r["parent_name"]) for r in preview["added"]] == [
            ("attachment", "Dagger", "Silvered")
        ]
        # It says so, and refuses nothing: a bridge's ordinary work is not breaking.
        assert preview["breaking"] == []
        assert [(b["kind"], b["reason"]) for b in preview["warnings"]] == [
            ("attachment", "attachment_added")
        ]
        assert "Silvered" in preview["warnings"][0]["detail"]
        ok = await w.author.put(f"/tenants/{bridge}/published", json={})
        assert ok.status_code == 200, ok.text
        release = ok.json()["release"]
        assert release["breaking"] is False and release["breaking_rows"] == []
        assert [(b["kind"], b["reason"]) for b in release["warning_rows"]] == [
            ("attachment", "attachment_added")
        ]

        # And taking it away is listed as removed, and is not breaking: the library only detaches.
        async with admin_session_factory() as session:
            await session.execute(
                delete(EntityPrototype).where(EntityPrototype.entity_id == copy_of_dagger)
            )
            await session.commit()
        gone = (await w.author.get(f"/tenants/{bridge}/release-preview")).json()
        assert gone["counts"]["attachments"] == {"added": 0, "removed": 1}
        assert gone["breaking"] == [] and gone["warnings"] == []
    finally:
        await w.done()


# --- The marks on a library's updates -----------------------------------------------------


async def test_updates_mark_each_row_released_or_edited_since_the_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        # Published: a rename, a new entry, and the removal of one.
        await _rename(w)
        await _added(w)
        await _removed(w)
        await w.publish(label="1.1", acknowledge_breaking=True)
        # Edited since, not published: a stat value, and one more new entry.
        await _stat_value(w)
        async with admin_session_factory() as session:
            session.add(Entity(tenant_id=w.repository, name="Spear"))
            await session.commit()

        updates = await w.updates()
        assert updates["release"]["label"] == "1.1"
        assert updates["release"]["id"]
        states = {r["name"]: r["state"] for r in updates["changed"]}
        # The library's own copy is named "Longsword": the row is the one that changed twice,
        # a rename that was released and a value that was not. It is edited, since the
        # repository's row is no longer what was released.
        assert states == {"Longsword": "edited"}
        assert {a["name"]: a["state"] for a in updates["added"]} == {
            "Blade": "released",
            "Spear": "edited",
        }
        assert [(r["name"], r["state"]) for r in updates["removed"]] == [("Orc", "released")]
    finally:
        await w.done()


async def test_a_row_edited_after_the_release_is_edited_and_one_before_it_is_released(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        await _rename(w)
        await w.publish(label="1.1")
        released = await w.updates()
        assert [(r["name"], r["state"]) for r in released["changed"]] == [("Longsword", "released")]

        # Removed after the release: edited. Its removal published: released.
        await _removed(w)
        assert [(r["name"], r["state"]) for r in (await w.updates())["removed"]] == [
            ("Orc", "edited")
        ]
        await w.publish(label="1.2", acknowledge_breaking=True)
        assert [(r["name"], r["state"]) for r in (await w.updates())["removed"]] == [
            ("Orc", "released")
        ]
    finally:
        await w.done()


async def test_attachments_on_updates_are_marked_too(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    bridge = await w.author.create_tenant("Armoury Plus", kind="repository")
    w.tenants.append(bridge)
    try:
        assert (
            await w.author.put(f"/tenants/{w.repository}/subscribers/{bridge}")
        ).status_code == 201
        assert (
            await w.author.post(f"/tenants/{bridge}/repositories/{w.repository}/copy", json={})
        ).status_code == 201
        async with admin_session_factory() as session:
            own = Entity(tenant_id=bridge, name="Silvered")
            session.add(own)
            await session.flush()
            session.add(Item(entity_id=own.id, tenant_id=bridge))
            await session.commit()
        assert (await w.author.put(f"/tenants/{bridge}/published", json={})).status_code == 200
        assert (await w.author.put(f"/tenants/{bridge}/subscribers/{w.table}")).status_code == 201
        assert (
            await w.author.put(f"/tenants/{w.repository}/subscribers/{w.table}")
        ).status_code in (200, 201)
        assert (
            await w.gm.post(f"/tenants/{w.table}/repositories/{bridge}/copy", json={})
        ).status_code == 201

        async with admin_session_factory() as session:
            ids = {
                name: entity_id
                for entity_id, name in await session.execute(
                    select(Entity.id, Entity.name).where(Entity.tenant_id == bridge)
                )
            }
            session.add(
                EntityPrototype(
                    entity_id=ids["Dagger"], prototype_id=ids["Silvered"], tenant_id=bridge
                )
            )
            await session.commit()
        listing = f"/tenants/{w.table}/repositories/{bridge}/updates"
        edited = (await w.gm.get(listing)).json()
        assert [(a["child_name"], a["state"]) for a in edited["attachments_added"]] == [
            ("Dagger", "edited")
        ]
        assert (await w.author.put(f"/tenants/{bridge}/published", json={})).status_code == 200
        released = (await w.gm.get(listing)).json()
        assert [(a["child_name"], a["state"]) for a in released["attachments_added"]] == [
            ("Dagger", "released")
        ]
        # The release that warned of it is on the row, in words, and none called it breaking.
        assert released["attachments_added"][0]["breaking"] == []
        (note,) = released["attachments_added"][0]["warnings"]
        assert note["reason"] == "attachment_added"
        assert "Silvered" in note["detail"]
    finally:
        await w.done()


# --- Confirming a breaking update ---------------------------------------------------------


def _apply(w: ReleaseWorld, actions: list[dict[str, Any]], **extra: Any) -> Awaitable[Any]:
    return w.gm.post(
        f"/tenants/{w.table}/repositories/{w.repository}/updates",
        json={"actions": actions, **extra},
    )


async def _breaking_world(raw_client: AsyncClient, jwks: FakeJwksServer) -> ReleaseWorld:
    """Copied at release 1.0; release 1.1 retypes Speed (breaking) and renames Longsword; release
    1.2 renames Dagger and is not breaking."""
    w = await release_world(raw_client, jwks, copied=True)
    await _value_type(w)
    await _rename(w)
    await w.publish(label="1.1", acknowledge_breaking=True)
    async with admin_session_factory() as session:
        (await session.get_one(Entity, w.ids["Dagger"])).name = "Knife"
        await session.commit()
    await w.publish(label="1.2")
    return w


async def test_updates_say_which_rows_a_release_since_the_copy_called_breaking(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _breaking_world(raw_client, fake_jwks_server)
    try:
        updates = await w.updates()
        notes = {r["name"]: r["breaking"] for r in updates["changed"]}
        assert notes["Longsword"] == [] and notes["Dagger"] == []
        (speed,) = notes["Speed"]
        assert speed["reason"] == "stat_definition_retyped"
        assert speed["release"]["label"] == "1.1"
        assert "int to text" in speed["detail"]
    finally:
        await w.done()


async def test_applying_a_breaking_row_needs_the_action_to_confirm_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _breaking_world(raw_client, fake_jwks_server)
    try:
        speed = {"kind": "stat_definition", "source_id": str(w.ids["Speed"]), "action": "apply"}
        dagger = {"kind": "entity", "source_id": str(w.ids["Dagger"]), "action": "apply"}

        refused = await _apply(w, [dagger, speed])
        assert refused.status_code == 409, refused.text
        problem = refused.json()
        assert problem["type"] == "update-needs-confirmation"
        assert [(u["kind"], u["name"], u["reason"]) for u in problem["unconfirmed"]] == [
            ("stat_definition", "Speed", "stat_definition_retyped")
        ]
        # Nothing was applied, not even the row that needed no asking, and a dry run asks too.
        assert (await _apply(w, [dagger, speed], dry_run=True)).status_code == 409
        assert [r["name"] for r in (await w.updates())["changed"]].count("Dagger") == 1

        ok = await _apply(w, [dagger, {**speed, "confirm": True}])
        assert ok.status_code == 200, ok.text
        assert ok.json()["applied"] == 2
    finally:
        await w.done()


async def test_a_library_that_has_taken_the_breaking_release_is_not_asked_again(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        await _value_type(w)
        await w.publish(label="1.1", acknowledge_breaking=True)
        speed = {"kind": "stat_definition", "source_id": str(w.ids["Speed"]), "action": "apply"}
        assert (await _apply(w, [speed])).status_code == 409
        assert (await _apply(w, [{**speed, "confirm": True}])).status_code == 200

        # The library is on 1.1 now. A later change to the same row, in a release that is not
        # breaking, is a plain update.
        async with admin_session_factory() as session:
            (await session.get_one(StatDefinition, w.ids["Speed"])).name = "Pace"
            await session.commit()
        await w.publish(label="1.2")
        (row,) = (r for r in (await w.updates())["changed"] if r["name"] == "Speed")
        assert row["breaking"] == []
        assert (await _apply(w, [speed])).status_code == 200
    finally:
        await w.done()


async def test_a_library_several_releases_behind_is_owed_everything_it_skipped(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        await _value_type(w)
        await w.publish(label="1.1", acknowledge_breaking=True)
        await _slug(w)
        await w.publish(label="1.2", acknowledge_breaking=True)
        await _rename(w)
        await w.publish(label="1.3")

        changed = {r["name"]: r["breaking"] for r in (await w.updates())["changed"]}
        assert [n["release"]["label"] for n in changed["Speed"]] == ["1.1"]
        # The slug changed in 1.2, the rename in 1.3: the row carries the one that is breaking.
        assert [(n["reason"], n["release"]["label"]) for n in changed["Longsword"]] == [
            ("slug_changed", "1.2")
        ]
    finally:
        await w.done()


async def test_a_copy_from_before_releases_is_owed_every_breaking_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        async with admin_session_factory() as session:
            await session.execute(
                update(RepositoryCopy)
                .where(RepositoryCopy.tenant_id == w.table)
                .values(synced_release_id=None)
            )
            await session.commit()
        await _value_type(w)
        await w.publish(label="1.1", acknowledge_breaking=True)
        speed = next(r for r in (await w.updates())["changed"] if r["name"] == "Speed")
        assert [n["release"]["label"] for n in speed["breaking"]] == ["1.1"]
    finally:
        await w.done()


async def test_detaching_a_row_that_was_removed_needs_no_confirmation(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        await _removed(w)
        await w.publish(label="1.1", acknowledge_breaking=True)
        updates = await w.updates()
        orc = updates["removed"][0]
        assert orc["name"] == "Orc"
        assert [n["reason"] for n in orc["breaking"]] == ["entity_removed"]
        done = await _apply(
            w, [{"kind": "entity", "source_id": orc["source_id"], "action": "detach"}]
        )
        assert done.status_code == 200, done.text
        assert done.json()["detached"] == 1
    finally:
        await w.done()


async def test_taking_an_attachment_a_release_warned_about_needs_naming_and_no_confirming(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    bridge = await w.author.create_tenant("Armoury Plus", kind="repository")
    w.tenants.append(bridge)
    try:
        assert (
            await w.author.put(f"/tenants/{w.repository}/subscribers/{bridge}")
        ).status_code == 201
        assert (
            await w.author.post(f"/tenants/{bridge}/repositories/{w.repository}/copy", json={})
        ).status_code == 201
        async with admin_session_factory() as session:
            own = Entity(tenant_id=bridge, name="Silvered")
            session.add(own)
            await session.flush()
            session.add(Item(entity_id=own.id, tenant_id=bridge))
            await session.commit()
        assert (await w.author.put(f"/tenants/{bridge}/published", json={})).status_code == 200
        assert (await w.author.put(f"/tenants/{bridge}/subscribers/{w.table}")).status_code == 201
        assert (
            await w.author.put(f"/tenants/{w.repository}/subscribers/{w.table}")
        ).status_code in (200, 201)
        assert (
            await w.gm.post(f"/tenants/{w.table}/repositories/{bridge}/copy", json={})
        ).status_code == 201
        async with admin_session_factory() as session:
            ids = {
                name: entity_id
                for entity_id, name in await session.execute(
                    select(Entity.id, Entity.name).where(Entity.tenant_id == bridge)
                )
            }
            session.add(
                EntityPrototype(
                    entity_id=ids["Dagger"], prototype_id=ids["Silvered"], tenant_id=bridge
                )
            )
            await session.commit()
        assert (await w.author.put(f"/tenants/{bridge}/published", json={})).status_code == 200
        updates = (await w.gm.get(f"/tenants/{w.table}/repositories/{bridge}/updates")).json()
        pair = updates["attachments_added"][0]
        attachment = {
            "child_source_id": pair["child_source_id"],
            "parent_source_id": pair["parent_source_id"],
            "action": "add",
        }
        url = f"/tenants/{w.table}/repositories/{bridge}/updates"
        # The warning is on the row for the library to read; naming the attachment is the decision.
        assert [n["reason"] for n in pair["warnings"]] == ["attachment_added"]
        ok = await w.gm.post(url, json={"actions": [], "attachments": [attachment]})
        assert ok.status_code == 200, ok.text
        assert ok.json()["attachments_added"] == 1
    finally:
        await w.done()


# --- Who may ask, and who sees what -------------------------------------------------------


async def test_only_the_repositorys_members_may_preview_a_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        assert (await w.gm.get(f"/tenants/{w.repository}/release-preview")).status_code in (
            403,
            404,
        )
        # A play tenant has nothing to release.
        assert (await w.gm.get(f"/tenants/{w.table}/release-preview")).status_code == 409
        # Nor is the preview a route of a library's reads of the repository.
        gated = await w.gm.get(f"/tenants/{w.table}/repositories/{w.repository}/release-preview")
        assert gated.status_code == 404
    finally:
        await w.done()


async def test_two_repositories_never_see_each_others_rows(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    other = await release_world(raw_client, fake_jwks_server)
    try:
        # The same names and the same shape, in two repositories, with ids of their own.
        mine, theirs = await w.preview(), await other.preview()
        assert mine["matches"] is True and theirs["matches"] is True
        assert mine["live_digest"] != theirs["live_digest"]
        await _removed(other)
        # Another repository's edit moves nothing here.
        assert (await w.preview())["differing_rows"] == 0
        assert (await other.preview())["differing_rows"] == 1
        async with admin_session_factory() as session:
            for repository in (w.repository, other.repository):
                rows = (
                    await session.execute(
                        select(RepositoryReleasedRow.kind, RepositoryReleasedRow.row_id).where(
                            RepositoryReleasedRow.tenant_id == repository
                        )
                    )
                ).all()
                assert len(rows) == 2 + 4 + 3
        # A release names its rows by the repository's own ids, which a library's copy link holds
        # as `source_id`.
        entities = {row_id for kind, row_id in rows if kind == "entity"}
        assert entities == {other.ids[n] for n in ("Longsword", "Dagger", "Orc")}
    finally:
        await other.done()
        await w.done()


async def test_the_database_shows_a_library_the_released_rows_only_through_the_gated_read(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server)
    stranger = await w.gm.create_tenant("Elsewhere")
    w.tenants.append(stranger)

    async def seen(*, tenant: uuid.UUID, reading: uuid.UUID | None) -> int:
        async with engine.connect() as conn, conn.begin():
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)}
            )
            await conn.execute(
                text("SELECT set_config('app.repository_tenant_id', :r, true)"),
                {"r": str(reading) if reading else ""},
            )
            count = await conn.execute(
                text("SELECT count(*) FROM repository_released_row WHERE tenant_id = :t"),
                {"t": w.repository},
            )
            return int(count.scalar_one())

    try:
        assert await seen(tenant=w.repository, reading=None) == 9
        assert await seen(tenant=w.table, reading=None) == 0
        assert await seen(tenant=stranger, reading=w.repository) == 0
        assert await seen(tenant=w.table, reading=w.repository) == 9
        # Never written by a library, which can read and not change what a repository released.
        async with engine.connect() as conn, conn.begin():
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(w.table)}
            )
            await conn.execute(
                text("SELECT set_config('app.repository_tenant_id', :r, true)"),
                {"r": str(w.repository)},
            )
            deleted = await conn.execute(
                text("DELETE FROM repository_released_row WHERE tenant_id = :t"),
                {"t": w.repository},
            )
            assert deleted.rowcount == 0
    finally:
        await w.done()
