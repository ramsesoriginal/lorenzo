# 0149 - Giving a pack from the API: `POST .../item-instances/from-pack`

Status: accepted

Slice 1 of [RFC 0032](../rfcs/0032-giving-a-pack-from-the-api.md) (§1-9). Builds on [ADR 0145](0145-pack-contents-in-the-description.md) (the list in the description), [ADR 0140](0140-a-stack-when-an-item-instance-is-created.md) (a stack in one create), [ADR 0128](0128-capacity-and-moving-anyway.md) (capacity) and [ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md) (groups own things).

## Context

ADR 0145 left handing a pack out to the CLI: read the list from the description, then one `POST /item-instances` per line. RFC 0032 moves it into the API, so it is one transaction any client can use. The list in the description stays the source; this ADR decides how the API reads it, what it creates for a being and for a group, and what refuses it.

## Decision

### The route

`POST /tenants/{tenant_id}/item-instances/from-pack`, body `GivePackRequest`:

- `pack_id`: an item of the tenant.
- `owner_entity_id`: a being or a group.
- `override`: default `false`.

`?dry_run=true` does all of it, checks included, and rolls it back. The answer is `PackGivenOut`: `pack_id`, `owner_entity_id`, `dry_run`, and `created`, a list of `PackItemOut` (an `ItemInstanceOut`, plus `children`, the same shape, for what's inside it). It is `201` for a real call and `200` for a dry run, whose ids name nothing. There is no `Location`: a call creates many things.

### Reading the list

`lorenzo_api/packs.py` holds the parser, pure and without a database. It is the grammar of the CLI's `importer/packs.py`:

- A line is `- N x [Label](slug)` or `- N x text`, indented two spaces per level.
- A line two levels or more below the line above it, or indented with nothing above it, is ignored, as is anything that isn't a line of that shape, a quantity below 1, and a level beyond the third.
- The slug is 1 to 100 characters of letters, digits, `_` and `-`, starting with a letter or digit.

`apps/api/tests/data/pack_lists.json` holds the examples, each a text and the lines and tree it reads as. The API's tests run every one, and the CLI's parser is held to them too (ADR 0150).

The text is the pack item's own **public description**: the payloads of its `description` information when `is_public`, in `order`, joined with a newline, only those with a description row. A GM-only description is never read, and nothing the caller can see changes the answer.

### What refuses it

All `422`, each its own problem type, none of them partial:

- **`not-a-pack`**: `pack_id` is not an item of the tenant, or its public description has no list.
- **`pack-list`**: the list can't be handed out as it is. It carries `lines`, what's wrong, one entry each:
  - a line without a link (`"Alms box"`);
  - a slug that isn't an item of the tenant (`"basic-gear-nope"`);
  - a quantity above 1000;
  - a top-level stack for a group above 50 (the CLI's own guard);
  - more than 200 instances to create.
- **`invalid-pack-owner`**: `owner_entity_id` is neither a `Being` nor named as a group by `group_member`. (An empty group isn't recognisable, a consequence of ADR 0028's data model that ADR 0045 already accepted.)

An owner that isn't an entity of the tenant is the usual `404`. Both are checked after authorization (below), which only admits a character the caller plays or whose campaign they GM, or a group with such a member; so today neither is reachable over HTTP. They are the guard for the day authorization is widened, and the service's tests call them directly.

### What it creates

The list is nested by indent: a line goes inside the nearest line above it one level up. Each is resolved to an item by its slug through `entity_slug`.

- A line with lines under it is a **container**: made once per unit of its quantity, each with its own copy of what's under it.
- A line with nothing under it is **one stack** of its quantity, as one instance with a `Containment` row whose `quantity` is the count (ADR 0140), inside its parent.
- An instance takes its item's name and is an instance of that item, as `POST /item-instances` makes one. Nothing is slugged.
- **Everything is owned by `owner_entity_id`.**
- **For a being**, each top-level instance is also contained directly in it: Equipped (ADR 0123).
- **For a group**, top-level instances are in no container, so a top-level stack of *n* is *n* single instances. What's inside a container is a stack as everywhere else.

The pack item itself is not instantiated.

### Who may

The caller must be allowed to create an instance for that owner: `_authorize_create_instance`, once. `override` is `_authorize_override`, a GM's alone, refused up front (`403 override-forbidden`). Both come before anything is read, so a caller who may not learns nothing of the pack, the owner or the list.

That is `POST /item-instances`'s own rule, and it has one consequence worth naming: a bare being (an NPC with no player) has no one with standing, so no one can be handed a pack yet. Giving things to NPCs is a gap in `_authorize_create_instance` that this slice neither opens nor closes.

### Capacity

One transaction; anything that raises leaves nothing. Capacity is checked as a create inside something is (ADR 0128), unless `override`:

- **A being.** One `CapacityCheck` on the being, started before anything is made and finished after the last top-level thing, with the top-level instances as what moved. It locks the being's chain and measures the whole load, contents included.
- **Each new container** gets its own, started after it exists and finished after what goes into it, so its own `containment_capacity`, `carry_capacity` and `max_item_size` hold.
- A group has no top-level check. A tenant with no capacity stats pays nothing (ADR 0128).
- The outer check's lock on the being's chain is what keeps two packs into one being in order, so `lock_ahead` isn't needed. Binding refuses a move or an owner change, never a create (ADR 0129), so there is nothing to skip.

Refused with `409 capacity-exceeded`, naming the container.

### What's recorded

- **Activity log**: one `item_instance.created` per instance, `detail` `prototype=<id>; pack=<id>`, with `; overridden` when `override` was sent, as ADR 0128 has it. Not written on a dry run.
- **Change feed**: one `record_change` for everything created, each with no holders before, so every holder is told what they received, once. Not written on a dry run.

### Code

- `packs.py`: the parser and the nesting, pure.
- `pack_giving.py`: what the route does after authorization: the owner check, reading the list, resolving the slugs, the plan with its limits, creating the rows and the checks. It writes the same rows `create_item_instance` does.
- `routers/item_instances.py`: the route, authorization, outputs, records and the dry-run rollback.
- Problem types `NotAPackError`, `PackListError`, `InvalidPackOwnerError` in `exceptions.py`.
- The OpenAPI schema changes, so `packages/api-client`'s and `apps/cli`'s generated code are regenerated in the same change.

## Not in scope

Everything RFC 0032 leaves out, plus: the CLI (slice 2), and a limit that adapts to a tenant's own settings. The limits are constants.

## Consequences

- A pack is handed out by one request, whole or not at all, to a being's hands or to a group.
- The API now parses prose with a convention in it. A careless edit to a description refuses the pack with the lines named, rather than skipping them.
- Two parsers of one grammar, held together by shared examples. The CLI's keeps the three-level rule only for what the importer writes, which is two.
- A group can't be handed a pack until it has a member, and neither can an unnamed empty entity.
- `ItemInstanceOut` is built once per created instance, so a call near the 200-instance limit does 200 view reads. Acceptable for something a person does by hand.
- The three problem types and the route are an additive change to the API's contract.
