# 0140 - A stack when an item instance is created: `ItemInstanceCreate.quantity`

Status: accepted

One of four small `apps/api` additions for [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R7, R11; slice 3). See [ADR 0139](0139-name-an-item-when-it-is-created.md).

## Context

A stack of identical things is one instance with a `Containment.quantity` above one ([ADR 0041](0041-containment-quantity-and-stacking.md)): five rations are one row, and splitting and merging work on it. But `POST /item-instances` cannot make one. Its containment row always has the default quantity of 1, so a stack is made by creating five instances and merging them, or by creating one and asking for more.

RFC 0025 R7 puts a pack's contents in its description, and a client that hands the pack out creates the container and then each thing inside it. "5 x Rations" should be one create.

## Decision

`ItemInstanceCreate` gains an optional `quantity`, a whole number of at least 1, defaulting to 1.

- It is the quantity of the instance's containment in `container_entity_id`, so it goes into the same `Containment` row.
- **It needs a container.** A quantity above one with no `container_entity_id` is refused with `422`: outside a container there is nowhere to hold a quantity, and `Containment` is the only place ADR 0041 keeps one. A quantity of 1 (the default) is always fine.
- The creation goes through the same capacity check as any other create into a container ([ADR 0128](0128-capacity-and-moving-anyway.md)); capacity already counts `weight × quantity` of what is inside, so a stack of five weighs five. `override` works as it does for a single item.
- Slugs, ownership and the activity log are unchanged.

## Consequences

- Additive and optional on the wire: no migration, and a caller that doesn't send it gets what it always did. The generated TypeScript types (`openapi-typescript`) make a field that has a default *required*, though, so the code in loot-bot and inventory-web that builds this body now sends `quantity: 1`, as it already sends `override: false`. That change ships with this one.
- Making a stack is one write, so it is atomic. A client that hands out a pack no longer needs a merge pass afterwards.
- One instance holding a quantity has one slug at most, and that slug names the whole stack; that is what a stack already is (ADR 0041).
