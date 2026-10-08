"""A repository with a bit of everything the update engine compares (RFC 0037 §2), for the
release tests (ADR 0208). Authored straight in the database, as its authors would through the
ordinary routes; publishing, previewing, copying and updating go through the HTTP API.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient

from lorenzo_api.models import (
    Being,
    ComputedStat,
    ComputedStatLinear,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    Item,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
)


@dataclass
class ReleaseWorld:
    author: Actor
    gm: Actor
    repository: uuid.UUID
    table: uuid.UUID
    # Names to ids: the repository's own rows.
    ids: dict[str, uuid.UUID]
    tenants: list[uuid.UUID] = field(default_factory=list)
    actors: list[Actor] = field(default_factory=list)

    async def done(self) -> None:
        await cleanup([self.table, self.repository, *self.tenants], [self.author, self.gm])

    async def publish(self, **body: Any) -> Any:
        response = await self.author.put(f"/tenants/{self.repository}/published", json=body)
        assert response.status_code == 200, response.text
        return response.json()["release"]

    async def preview(self) -> dict[str, Any]:
        response = await self.author.get(f"/tenants/{self.repository}/release-preview")
        assert response.status_code == 200, response.text
        return response.json()  # type: ignore[no-any-return]

    async def releases(self) -> list[dict[str, Any]]:
        response = await self.author.get(f"/tenants/{self.repository}/releases")
        assert response.status_code == 200, response.text
        return response.json()["items"]  # type: ignore[no-any-return]

    async def updates(self) -> dict[str, Any]:
        response = await self.gm.get(
            f"/tenants/{self.table}/repositories/{self.repository}/updates"
        )
        assert response.status_code == 200, response.text
        return response.json()  # type: ignore[no-any-return]

    async def copy(self) -> None:
        copied = await self.gm.post(
            f"/tenants/{self.table}/repositories/{self.repository}/copy", json={}
        )
        assert copied.status_code == 201, copied.text


async def release_world(
    raw_client: AsyncClient, jwks: FakeJwksServer, *, published: bool = True, copied: bool = False
) -> ReleaseWorld:
    """Armoury: an Abilities group with Strength, Speed (ints, one with a value), Mood (an
    enum with calm and angry) and Damage (computed from Strength); an empty Extras group;
    Longsword (an item with a link name, a stat group, a stat and the formula), Dagger (an item
    whose parent is Longsword), and Orc (a being). Published as release "1.0" if asked, and
    copied by a library, `table`, if asked."""
    author = await make_actor(raw_client, jwks, "author")
    gm = await make_actor(raw_client, jwks, "gm")
    repository = await author.create_tenant("Armoury", kind="repository")
    table = await gm.create_tenant("My Table")
    async with admin_session_factory() as session:
        abilities = StatGroup(tenant_id=repository, name="Abilities")
        extras = StatGroup(tenant_id=repository, name="Extras")
        entities = {
            name: Entity(tenant_id=repository, name=name) for name in ("Longsword", "Dagger", "Orc")
        }
        session.add_all([abilities, extras, *entities.values()])
        await session.flush()

        def definition(name: str, value_type: StatValueType) -> StatDefinition:
            return StatDefinition(
                tenant_id=repository,
                stat_group_id=abilities.id,
                name=name,
                value_type=value_type,
            )

        strength = definition("Strength", StatValueType.INT)
        speed = definition("Speed", StatValueType.INT)
        mood = definition("Mood", StatValueType.ENUM)
        damage = definition("Damage", StatValueType.INT)
        session.add_all([strength, speed, mood, damage])
        await session.flush()
        longsword, dagger, orc = (entities[n].id for n in ("Longsword", "Dagger", "Orc"))
        session.add_all(
            [
                Item(entity_id=longsword, tenant_id=repository),
                Item(entity_id=dagger, tenant_id=repository),
                Being(entity_id=orc, tenant_id=repository),
                EntitySlug(entity_id=longsword, tenant_id=repository, slug="longsword"),
                EntityStatGroup(
                    entity_id=longsword, stat_group_id=abilities.id, tenant_id=repository
                ),
                EntityStat(
                    entity_id=longsword,
                    stat_definition_id=strength.id,
                    tenant_id=repository,
                    value_int=10,
                ),
                EntityPrototype(entity_id=dagger, prototype_id=longsword, tenant_id=repository),
                StatDefinitionEnumValue(
                    tenant_id=repository, stat_definition_id=mood.id, value="calm"
                ),
                StatDefinitionEnumValue(
                    tenant_id=repository, stat_definition_id=mood.id, value="angry"
                ),
                ComputedStat(
                    entity_id=longsword, stat_definition_id=damage.id, tenant_id=repository
                ),
            ]
        )
        await session.flush()
        session.add(
            ComputedStatLinear(
                entity_id=longsword,
                stat_definition_id=damage.id,
                tenant_id=repository,
                source_stat_definition_id=strength.id,
                multiplier=Decimal("0.5"),
                offset=Decimal("1"),
                round_mode="floor",
            )
        )
        await session.commit()
        ids = {name: e.id for name, e in entities.items()} | {
            "Abilities": abilities.id,
            "Extras": extras.id,
            "Strength": strength.id,
            "Speed": speed.id,
            "Mood": mood.id,
            "Damage": damage.id,
        }
    world = ReleaseWorld(author, gm, repository, table, ids)
    assert (await author.put(f"/tenants/{repository}/subscribers/{table}")).status_code == 201
    if published:
        await world.publish(label="1.0")
    if copied:
        await world.copy()
    return world
