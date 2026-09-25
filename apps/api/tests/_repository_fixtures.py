"""One row in every repository content table (ADR 0118) - for the RLS
tests, which need each table to have something to hide or show.
"""

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    Being,
    Character,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatLinear,
    Containment,
    ContentReference,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    GroupMember,
    Information,
    Item,
    ItemInstance,
    Knowledge,
    Ownership,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
)


async def seed_every_content_table(
    session: AsyncSession, tenant_id: uuid.UUID, *, with_copy_records: bool = False
) -> None:
    """Flushes, doesn't commit. `with_copy_records` adds a copy record and
    one copy link of each kind, as if this tenant had copied something -
    for the RLS tests, which need a row in every table; a tenant copying
    this one would then see those rows as copies, not its own.
    """

    def entity(name: str) -> Entity:
        e = Entity(tenant_id=tenant_id, name=name)
        session.add(e)
        return e

    sword, blade, chest, guild, elminster = (
        entity("Sword"),
        entity("Blade"),
        entity("Chest"),
        entity("Harpers"),
        entity("Elminster"),
    )
    group = StatGroup(tenant_id=tenant_id, name="Abilities")
    session.add(group)
    await session.flush()

    strength = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Strength", value_type=StatValueType.INT
    )
    modifier = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Modifier", value_type=StatValueType.INT
    )
    strong = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Strong", value_type=StatValueType.BOOL
    )
    alignment = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Alignment", value_type=StatValueType.ENUM
    )
    session.add_all([strength, modifier, strong, alignment])
    session.add_all(
        [
            Item(entity_id=sword.id, tenant_id=tenant_id),
            ItemInstance(entity_id=blade.id, tenant_id=tenant_id),
            Item(entity_id=chest.id, tenant_id=tenant_id),
            Being(entity_id=elminster.id, tenant_id=tenant_id),
        ]
    )
    await session.flush()
    session.add_all(
        [
            Character(entity_id=elminster.id, tenant_id=tenant_id),
            StatDefinitionEnumValue(
                tenant_id=tenant_id, stat_definition_id=alignment.id, value="neutral"
            ),
            EntityPrototype(entity_id=blade.id, prototype_id=sword.id, tenant_id=tenant_id),
            EntitySlug(entity_id=sword.id, tenant_id=tenant_id, slug=f"sword-{uuid.uuid4().hex}"),
            EntityStatGroup(entity_id=sword.id, stat_group_id=group.id, tenant_id=tenant_id),
            EntityStat(
                entity_id=sword.id,
                stat_definition_id=strength.id,
                tenant_id=tenant_id,
                value_int=16,
            ),
            ComputedStat(entity_id=sword.id, stat_definition_id=modifier.id, tenant_id=tenant_id),
            ComputedStat(entity_id=sword.id, stat_definition_id=strong.id, tenant_id=tenant_id),
            Containment(child_entity_id=blade.id, parent_entity_id=chest.id, tenant_id=tenant_id),
            Ownership(owned_entity_id=blade.id, owner_character_id=guild.id, tenant_id=tenant_id),
        ]
    )
    await session.flush()
    session.add_all(
        [
            ComputedStatLinear(
                entity_id=sword.id,
                stat_definition_id=modifier.id,
                tenant_id=tenant_id,
                source_stat_definition_id=strength.id,
                multiplier=Decimal("0.5"),
                offset=Decimal("-5"),
                round_mode="floor",
            ),
            ComputedStatComparison(
                entity_id=sword.id,
                stat_definition_id=strong.id,
                tenant_id=tenant_id,
                left_stat_definition_id=strength.id,
                comparator="ge",
                right_constant=Decimal("15"),
            ),
            GroupMember(
                group_entity_id=guild.id, character_entity_id=elminster.id, tenant_id=tenant_id
            ),
        ]
    )
    info = Information(
        tenant_id=tenant_id, entity_id=sword.id, title="Lore", type="description", is_public=True
    )
    session.add(info)
    await session.flush()
    payloads = [Payload(tenant_id=tenant_id, information_id=info.id, order=i) for i in range(4)]
    session.add_all(payloads)
    await session.flush()
    session.add_all(
        [
            PayloadDescription(
                payload_id=payloads[0].id,
                tenant_id=tenant_id,
                locale="en",
                content="Forged for [[elminster]].",
            ),
            PayloadNumber(payload_id=payloads[1].id, tenant_id=tenant_id, value=Decimal("3")),
            PayloadPicture(
                payload_id=payloads[2].id, tenant_id=tenant_id, data=b"\x89PNG", file_type="png"
            ),
            PayloadDocument(
                payload_id=payloads[3].id,
                tenant_id=tenant_id,
                data=b"%PDF",
                filename="lore.pdf",
                file_type="pdf",
            ),
            ContentReference(
                payload_id=payloads[0].id,
                position=0,
                tenant_id=tenant_id,
                kind="entity",
                target="elminster",
            ),
            Knowledge(tenant_id=tenant_id, knower_entity_id=elminster.id, information_id=info.id),
        ]
    )
    if not with_copy_records:
        await session.flush()
        return
    # As if this tenant had copied something itself (ADR 0119): a bridge's
    # copy records are content its subscribers read (ADR 0120).
    upstream = uuid.uuid4()
    link = {"tenant_id": tenant_id, "source_tenant_id": upstream, "snapshot": {}}
    session.add_all(
        [
            RepositoryCopy(tenant_id=tenant_id, repository_tenant_id=upstream),
            RepositoryCopyLinkEntity(**link, entity_id=chest.id, source_id=uuid.uuid4()),
            RepositoryCopyLinkStatGroup(
                **link, stat_group_id=group.id, source_id=uuid.uuid4(), mode="copied"
            ),
            RepositoryCopyLinkStatDefinition(
                **link, stat_definition_id=strength.id, source_id=uuid.uuid4(), mode="copied"
            ),
        ]
    )
    await session.flush()
